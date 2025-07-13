# agents/content_generation.py
import json
import hashlib
import os
from stability_sdk import client as stability_client
from google.cloud import texttospeech_v1beta1 as texttospeech
# from moviepy.editor import VideoFileClip, CompositeVideoClip, ImageClip, AudioFileClip, concatenate_videoclips # For video editing
from moviepy.editor import *  # Import all for simplicity in blueprint, but be specific in production
from moviepy.video.tools.subtitles import SubtitlesClip  # For subtitles if desired
import random
from config.settings import (
    MIN_ARTICLE_LENGTH_WORDS, MAX_ARTICLE_LENGTH_WORDS, AI_CONTENT_DISCLAIMER_TEXT,
    AI_CONTENT_DISCLAIMER_ENABLED, NICHE_TOPIC, STABILITY_AI_API_KEY,
    GCP_PROJECT_ID, VIDEO_GENERATION_SETTINGS, DATA_DIR
)
from database.db_manager import DBManager
from database.models import StructuredFact, GeneratedContent
from utils.logger import setup_logger
from utils.llm_interface import LLMInterface
from utils.file_manager import save_content_file, save_json
from utils.prompt_templates import (
    ARTICLE_GENERATION_PROMPT_HI, ARTICLE_GENERATION_PROMPT_EN,
    IMAGE_PROMPT_GENERATION_PROMPT, VIDEO_SCRIPT_SUMMARY_PROMPT
)

logger = setup_logger("ContentGenerationAgent")
db_manager = DBManager()
llm_interface = LLMInterface()

# Initialize Stability AI client for image generation
stability_api = None
if STABILITY_AI_API_KEY:
    try:
        stability_api = stability_client.StabilityInference(key=STABILITY_AI_API_KEY, verbose=True)
        logger.info("Stability AI client initialized.")
    except Exception as e:
        logger.error(f"Failed to initialize Stability AI client: {e}")

# Initialize Google Cloud Text-to-Speech client
tts_client = None
if GCP_PROJECT_ID:
    try:
        tts_client = texttospeech.TextToSpeechClient()
        logger.info("Google Cloud Text-to-Speech client initialized.")
    except Exception as e:
        logger.error(f"Failed to initialize Google Cloud Text-to-Speech client: {e}")


class ContentGenerationAgent:
    """
    Agent responsible for generating various forms of content (articles, images, videos)
    from structured facts.
    """

    def generate_article(self, structured_fact_id: int, target_language: str,
                         keywords: list[str] | None = None) -> int | None:
        """
        Generates a comprehensive article based on structured facts.
        Returns the ID of the GeneratedContent record, or None on failure/duplicate.
        """
        structured_fact = db_manager.get_record_by_id(StructuredFact, structured_fact_id)
        if not structured_fact:
            logger.error(f"Structured fact {structured_fact_id} not found for article generation.")
            return None

        logger.info(f"Generating article for structured fact ID: {structured_fact_id} in {target_language}")

        structured_data_json = json.dumps(structured_fact.data, indent=2, ensure_ascii=False)
        seo_keywords_str = ", ".join(keywords) if keywords else ""

        # Select appropriate prompt template based on language
        if target_language == "hi":
            prompt_template = ARTICLE_GENERATION_PROMPT_HI
            lang_keywords_param = "seo_keywords_hindi"
        elif target_language == "en":
            prompt_template = ARTICLE_GENERATION_PROMPT_EN
            lang_keywords_param = "seo_keywords_english"
        else:
            logger.error(f"Unsupported target language for article generation: {target_language}")
            return None

        disclaimer_text = AI_CONTENT_DISCLAIMER_TEXT if AI_CONTENT_DISCLAIMER_ENABLED else ""

        prompt = prompt_template.format(
            structured_data_json=structured_data_json,
            **{lang_keywords_param: seo_keywords_str},
            min_length=MIN_ARTICLE_LENGTH_WORDS,
            ai_disclaimer_text=disclaimer_text
        )

        generated_text = llm_interface.generate_text(prompt, model_choice="gemini", max_tokens=MAX_ARTICLE_LENGTH_WORDS)
        if not generated_text:
            logger.error(f"Failed to generate text for structured fact ID: {structured_fact_id}. LLM response empty.")
            structured_fact.is_processed_for_content = False  # Mark as not processed if generation failed
            db_manager.update_record(structured_fact)
            return None

        # Basic AI-powered quality check (can be expanded)
        if not self._perform_article_quality_check(generated_text, structured_fact.data, keywords):
            logger.warning(f"Generated article for {structured_fact_id} failed quality check. Not saving.")
            structured_fact.is_processed_for_content = False
            db_manager.update_record(structured_fact)
            return None

        # Calculate content hash for deduplication
        content_hash = hashlib.md5(generated_text.encode('utf-8')).hexdigest()
        if db_manager.is_content_hash_exists(content_hash):
            logger.info(f"Generated article for {structured_fact_id} is a duplicate (content hash). Skipping.")
            structured_fact.is_processed_for_content = True  # Mark as processed, as we've seen this content before
            db_manager.update_record(structured_fact)
            return None

        # Extract title from generated text (assuming LLM puts it in H1)
        # This is a simple heuristic; more robust parsing might be needed.
        title_match = generated_text.split('\n')[0].replace('#', '').strip()
        if not title_match:
            title_match = f"{NICHE_TOPIC} Guide {structured_fact_id}"  # Fallback title

        generated_content = GeneratedContent(
            title=title_match,
            body_html=generated_text,  # Assuming Markdown, will be converted to HTML later
            language=target_language,
            content_type="ARTICLE",
            keywords=keywords,
            content_hash=content_hash,
            status="GENERATED"
        )
        inserted_content = db_manager.insert_record(generated_content)

        if inserted_content:
            structured_fact.is_processed_for_content = True  # Mark as processed
            db_manager.update_record(structured_fact)
            logger.info(
                f"Successfully generated and saved article for {structured_fact_id}. Content ID: {inserted_content.id}")
            return inserted_content.id
        else:
            logger.error(f"Failed to save generated content for {structured_fact_id} to DB.")
            structured_fact.is_processed_for_content = False
            db_manager.update_record(structured_fact)
            return None

    def generate_images_for_content(self, generated_content_id: int) -> list[str]:
        """
        Generates illustrative images based on article content using Stability AI.
        Returns a list of local file paths to generated images.
        """
        generated_content = db_manager.get_record_by_id(GeneratedContent, generated_content_id)
        if not generated_content:
            logger.error(f"Generated content {generated_content_id} not found for image generation.")
            return []

        logger.info(f"Generating images for content ID: {generated_content_id}")

        if not stability_api:
            logger.warning("Stability AI not initialized. Skipping image generation.")
            return []

        # Use LLM to extract key visual concepts from the article text
        prompt = IMAGE_PROMPT_GENERATION_PROMPT.format(article_text=generated_content.body_html[:5000])
        image_prompts_json = llm_interface.generate_text(prompt, model_choice="gemini", max_tokens=500, temperature=0.5)

        image_prompts = []
        try:
            image_prompts = json.loads(image_prompts_json)
            if not isinstance(image_prompts, list): raise ValueError("Expected list of image prompts.")
        except (json.JSONDecodeError, ValueError):
            logger.warning(f"Could not parse image prompts JSON for {generated_content_id}. Generating default images.")
            # Fallback to a default, generic prompt
            image_prompts = [{"concept": generated_content.title,
                              "prompt": f"A farmer checking a small solar water pump system in a field in Rajasthan, India, sunny day, realistic, high detail."}]

        generated_image_paths = []
        for i, img_prompt_data in enumerate(image_prompts):
            prompt_text = img_prompt_data.get("prompt", f"Illustration for {img_prompt_data.get('concept', 'content')}")
            try:
                # Stability AI generation call
                response = stability_api.generate(
                    prompt=prompt_text,
                    width=768,  # Recommended size for web
                    height=768,
                    steps=50,  # Number of diffusion steps
                    cfg_scale=7.0,  # Classifier-free guidance scale
                    samples=1,  # Number of images to generate
                    seed=random.randint(0, 4294967295)  # Random seed for variety
                )

                for artifact in response.artifacts:
                    if artifact.finish_reason == stability_client.FinishReason.FILTER:
                        logger.warning(f"Image generation filtered for {prompt_text} (content policy).")
                        continue
                    if artifact.type == stability_client.ArtifactType.IMAGE:
                        img_filename = f"{generated_content_id}_img_{i}_{hashlib.md5(prompt_text.encode()).hexdigest()[:8]}.png"
                        img_path = save_content_file(artifact.binary, img_filename,
                                                     directory=f"content_assets/images/{generated_content_id}",
                                                     binary_mode=True)
                        generated_image_paths.append(img_path)
                        logger.info(f"Generated image for {generated_content.id}: {img_path}")
            except Exception as e:
                logger.error(
                    f"Stability AI image generation error for {generated_content_id} with prompt '{prompt_text}': {e}")

        # Update GeneratedContent with image paths
        generated_content.associated_images = generated_image_paths
        db_manager.update_record(generated_content)
        return generated_image_paths

    def generate_video_for_content(self, generated_content_id: int) -> str | None:
        """
        Generates a short explainer video based on key points from the content.
        This is a complex module, simplified for blueprint.
        """
        generated_content = db_manager.get_record_by_id(GeneratedContent, generated_content_id)
        if not generated_content:
            logger.error(f"Generated content {generated_content_id} not found for video generation.")
            return None

        logger.info(f"Generating video for content ID: {generated_content_id}")

        if not tts_client:
            logger.warning("Google Cloud Text-to-Speech not initialized. Skipping video generation.")
            return None
        if not stability_api:
            logger.warning("Stability AI not initialized for video visuals. Skipping video generation.")
            return None

        # 1. Summarize content into a video script using LLM
        prompt = VIDEO_SCRIPT_SUMMARY_PROMPT.format(
            max_duration_seconds=VIDEO_GENERATION_SETTINGS['max_duration_seconds'],
            language_name=generated_content.language,
            article_text=generated_content.body_html[:5000]
        )
        video_script_text = llm_interface.generate_text(prompt, model_choice="gemini", max_tokens=500, temperature=0.7)
        if not video_script_text:
            logger.error(f"Failed to generate video script for {generated_content_id}.")
            return None

        # 2. Convert script to audio
        language_code = VIDEO_GENERATION_SETTINGS['voice_language_code'].get(generated_content.language, 'en-IN')
        voice_name = VIDEO_GENERATION_SETTINGS['voice_name'].get(generated_content.language, 'en-IN-Wavenet-D')

        synthesis_input = texttospeech.SynthesisInput(text=video_script_text)
        voice = texttospeech.VoiceSelectionParams(language_code=language_code, name=voice_name)
        audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.MP3)

        try:
            tts_response = tts_client.synthesize_speech(input=synthesis_input, voice=voice, audio_config=audio_config)
            audio_filename = f"{generated_content_id}_narration.mp3"
            audio_path = save_content_file(tts_response.audio_content, audio_filename,
                                           directory=f"content_assets/audio/{generated_content_id}", binary_mode=True)
            logger.info(f"Generated audio: {audio_path}")
        except Exception as e:
            logger.error(f"Google TTS error for {generated_content_id}: {e}")
            return None

        # 3. Generate visuals (simplified: create a few images and combine)
        # This is a simplified approach. A real system would parse script for scene changes.
        visual_prompts_for_video = [
            f"A farmer looking at a solar pump in a field in Rajasthan, India, sunny day. ({generated_content.language})",
            f"Close-up of solar panels being cleaned. ({generated_content.language})",
            f"Diagram showing water flowing from a solar pump to crops. ({generated_content.language})",
            f"Farmers discussing a government scheme with documents. ({generated_content.language})"
        ]
        video_clips = []
        for i, v_prompt in enumerate(visual_prompts_for_video):
            try:
                response = stability_api.generate(prompt=v_prompt, width=1024, height=576, steps=30,
                                                  samples=1)  # 16:9 aspect ratio
                for artifact in response.artifacts:
                    if artifact.type == stability_client.ArtifactType.IMAGE:
                        img_filename = f"{generated_content_id}_video_frame_{i}.png"
                        img_path = save_content_file(artifact.binary, img_filename,
                                                     directory=f"content_assets/video_frames/{generated_content_id}",
                                                     binary_mode=True)
                        video_clips.append(ImageClip(img_path))
                        break  # Take the first image
            except Exception as e:
                logger.error(
                    f"Failed to generate video visual for {generated_content_id} with prompt '{v_prompt}': {e}")

        if not video_clips:
            logger.error(f"No visuals generated for video {generated_content_id}. Skipping video creation.")
            return None

        # 4. Assemble video with MoviePy
        try:
            audio_clip = AudioFileClip(audio_path)

            # Distribute audio duration across clips
            clip_duration = audio_clip.duration / len(video_clips)
            final_clips = [clip.set_duration(clip_duration).set_fps(24) for clip in
                           video_clips]  # Set FPS for smooth video

            final_video_clip = concatenate_videoclips(final_clips, method="compose")
            final_video_clip = final_video_clip.set_audio(audio_clip)

            video_output_dir = os.path.join(DATA_DIR, f"content_assets/videos/{generated_content_id}")
            os.makedirs(video_output_dir, exist_ok=True)
            video_output_path = os.path.join(video_output_dir, f"{generated_content_id}_final.mp4")

            final_video_clip.write_videofile(video_output_path, codec="libx264", audio_codec="aac", fps=24)
            logger.info(f"Video generated at {video_output_path}")

            generated_content.associated_video_path = video_output_path
            db_manager.update_record(generated_content)
            return video_output_path

        except Exception as e:
            logger.error(f"Error assembling video for {generated_content_id}: {e}")
            return None

    def _perform_article_quality_check(self, text: str, structured_data: dict, keywords: list[str] | None) -> bool:
        """
        Performs basic quality checks on the generated article.
        Can be expanded with more sophisticated NLP checks.
        """
        # 1. Length check
        if len(text.split()) < MIN_ARTICLE_LENGTH_WORDS:
            logger.warning(f"Quality check failed for length: Article too short ({len(text.split())} words).")
            return False

        # 2. Basic keyword presence (optional, depending on strictness)
        if keywords:
            text_lower = text.lower()
            missing_keywords = [kw for kw in keywords if kw.lower() not in text_lower]
            if missing_keywords:
                logger.warning(f"Quality check: Missing keywords in article: {missing_keywords}")
                # return False # Uncomment if keywords are mandatory for quality

        # 3. Check for obvious placeholders or LLM errors
        if "I cannot fulfill that request" in text or "As an AI language model" in text:
            logger.warning("Quality check: LLM boilerplate detected.")
            return False

        # 4. Check if main structured data points are covered (LLM-assisted check)
        # This would involve another LLM call:
        # prompt = f"Does the following article cover all the key points from this structured data? Article: {text[:2000]}, Data: {json.dumps(structured_data)}. Respond with YES/NO."
        # response = llm_interface.generate_text(prompt)
        # if response and "NO" in response.upper():
        #     logger.warning("Quality check: Article does not cover all key structured data points.")
        #     return False

        return True

