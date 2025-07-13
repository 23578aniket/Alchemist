# agents/seo_distribution.py
import requests
import base64
import json
import os
# For YouTube API, you'd need google-api-python-client and google-auth-oauthlib
# from google.oauth2.credentials import Credentials
# from google_auth_oauthlib.flow import InstalledAppFlow
# from google.auth.transport.requests import Request
# from googleapiclient.discovery import build
# from googleapiclient.errors import HttpError
# from googleapiclient.http import MediaFileUpload

from config.settings import (
    WORDPRESS_API_URL, WORDPRESS_USERNAME, WORDPRESS_APP_PASSWORD,
    YOUTUBE_API_KEY, NICHE_TOPIC, DATA_DIR
)
from database.db_manager import DBManager
from database.models import GeneratedContent, PublishedContent
from utils.logger import setup_logger
from utils.llm_interface import LLMInterface
from utils.prompt_templates import SEO_OPTIMIZATION_PROMPT

logger = setup_logger("SEODistributionAgent")
db_manager = DBManager()
llm_interface = LLMInterface()


class SEODistributionAgent:
    """
    Agent responsible for optimizing content for SEO and publishing it to various platforms.
    """

    def optimize_content_seo(self, generated_content_id: int) -> dict | None:
        """
        Uses LLM to generate SEO meta data and internal linking suggestions for content.
        Updates the GeneratedContent record with this data.
        """
        content = db_manager.get_record_by_id(GeneratedContent, generated_content_id)
        if not content:
            logger.error(f"Content {generated_content_id} not found for SEO optimization.")
            return None

        logger.info(f"Optimizing SEO for content ID: {generated_content_id}")

        prompt = SEO_OPTIMIZATION_PROMPT.format(
            article_title=content.title,
            niche_topic=NICHE_TOPIC,
            article_text=content.body_html[:5000]  # Limit input to LLM token window
        )

        seo_suggestions_json = llm_interface.generate_text(prompt, model_choice="gemini", max_tokens=500,
                                                           temperature=0.3)
        if not seo_suggestions_json:
            logger.error(f"Failed to get SEO suggestions for {generated_content_id}.")
            return None

        try:
            seo_data = json.loads(seo_suggestions_json)
            # Validate basic structure
            if not all(k in seo_data for k in ["meta_title", "meta_description", "internal_links"]):
                raise ValueError("Invalid SEO suggestions JSON structure.")

            content.meta_data = seo_data  # Store SEO data in the 'meta_data' JSON column
            db_manager.update_record(content)
            logger.info(f"SEO optimized for {generated_content_id}. Meta Title: {seo_data.get('meta_title')}")
            return seo_data
        except json.JSONDecodeError as e:
            logger.error(
                f"Failed to parse SEO suggestions JSON for {generated_content_id}: {e} -> {seo_suggestions_json[:500]}")
            return None
        except ValueError as e:
            logger.error(f"SEO suggestions validation failed for {generated_content_id}: {e}")
            return None

    def publish_to_wordpress(self, generated_content_id: int) -> str | None:
        """
        Publishes content to a headless WordPress instance via its REST API.
        Returns the published URL or None on failure.
        """
        content = db_manager.get_record_by_id(GeneratedContent, generated_content_id)
        if not content:
            logger.error(f"Content {generated_content_id} not found for WordPress publishing.")
            return None
        if content.status == "PUBLISHED":
            logger.info(f"Content {generated_content_id} already published. Skipping.")
            return None  # Or return existing URL

        logger.info(f"Publishing content ID: {generated_content_id} to WordPress.")

        wp_api_url = f"{WORDPRESS_API_URL}/wp/v2/posts"
        credentials = f"{WORDPRESS_USERNAME}:{WORDPRESS_APP_PASSWORD}"
        token = base64.b64encode(credentials.encode()).decode('utf-8')
        headers = {'Authorization': f'Basic {token}'}

        featured_media_id = None
        if content.associated_images:
            try:
                # Upload the first associated image as featured image
                featured_media_id = self._upload_image_to_wp_media(content.associated_images[0], headers)
            except Exception as e:
                logger.error(f"Failed to upload featured image for {generated_content_id}: {e}")
                # Continue publishing without featured image if upload fails

        # You would need to map your niche categories to WordPress category IDs.
        # For simplicity, using a default category ID (e.g., 1 for 'Uncategorized').
        # In a real setup, this would be dynamic based on content.niche_category.
        wp_categories = [1]

        # Convert Markdown to HTML if necessary (WordPress usually handles basic Markdown)
        # For complex Markdown, use a library like `markdown` or `markdown2`
        # import markdown
        # post_content_html = markdown.markdown(content.body_html)
        post_content_html = content.body_html  # Assuming LLM output is already HTML-like or simple Markdown

        post_data = {
            "title": content.title,
            "content": post_content_html,
            "status": "publish",
            "categories": wp_categories,
            "lang": content.language,  # Requires WPML or Polylang plugin for multi-language
            "featured_media": featured_media_id,
            "meta": {
                "_yoast_wpseo_metadesc": content.meta_data.get('meta_description', '') if content.meta_data else '',
                "_yoast_wpseo_title": content.meta_data.get('meta_title', '') if content.meta_data else ''
            }
        }

        try:
            response = requests.post(wp_api_url, headers=headers, json=post_data, timeout=60)
            response.raise_for_status()
            published_data = response.json()
            external_url = published_data.get('link')

            published_record = PublishedContent(
                generated_content_id=generated_content_id,
                platform="WORDPRESS",
                external_url=external_url
            )
            db_manager.insert_record(published_record)
            content.status = "PUBLISHED"
            db_manager.update_record(content)
            logger.info(f"Successfully published content {generated_content_id} to WordPress: {external_url}")
            return external_url

        except requests.exceptions.RequestException as e:
            logger.error(
                f"WordPress publishing failed for {generated_content_id}: {e} - Response: {getattr(e, 'response', 'No response').text}")
            content.status = "ERROR_PUBLISH"
            db_manager.update_record(content)
            return None
        except Exception as e:
            logger.error(f"Unexpected error during WordPress publishing for {generated_content_id}: {e}")
            content.status = "ERROR_PUBLISH"
            db_manager.update_record(content)
            return None

    def _upload_image_to_wp_media(self, image_path: str, headers: dict) -> int | None:
        """
        Helper function to upload an image file to WordPress Media Library.
        Returns the media ID on success.
        """
        media_api_url = f"{WORDPRESS_API_URL}/wp/v2/media"
        headers_media = headers.copy()
        headers_media['Content-Disposition'] = f'attachment; filename="{os.path.basename(image_path)}"'
        # Determine content type dynamically or assume PNG
        headers_media['Content-Type'] = 'image/png'

        try:
            with open(image_path, 'rb') as f:
                image_data = f.read()
            response = requests.post(media_api_url, headers=headers_media, data=image_data, timeout=30)
            response.raise_for_status()
            logger.info(f"Image {os.path.basename(image_path)} uploaded to WP media. ID: {response.json()['id']}")
            return response.json()['id']
        except requests.exceptions.RequestException as e:
            logger.error(
                f"Error uploading image {image_path} to WP media: {e} - Response: {getattr(e, 'response', 'No response').text}")
            raise  # Re-raise to be caught by publishing function
        except Exception as e:
            logger.error(f"Unexpected error during image upload to WP media {image_path}: {e}")
            raise

    def publish_to_youtube(self, generated_content_id: int) -> str | None:
        """
        Publishes video content to YouTube. This requires Google OAuth 2.0 setup.
        This is a highly simplified placeholder. Full implementation is complex.
        """
        content = db_manager.get_record_by_id(GeneratedContent, generated_content_id)
        if not content or not content.associated_video_path or not os.path.exists(content.associated_video_path):
            logger.error(
                f"Video content {generated_content_id} not found or video file missing for YouTube publishing.")
            return None
        if content.status == "PUBLISHED":  # Check if already published
            published_record = db_manager.query_records(PublishedContent, generated_content_id=generated_content_id,
                                                        platform="YOUTUBE")
            if published_record:
                logger.info(
                    f"Video content {generated_content_id} already published to YouTube: {published_record[0].external_url}. Skipping.")
                return published_record[0].external_url

        logger.info(f"Publishing video content ID: {generated_content_id} to YouTube.")

        # --- IMPORTANT: YouTube API requires OAuth 2.0 ---
        # This part cannot be fully automated without an initial manual consent flow.
        # You would typically:
        # 1. Download client_secrets.json from Google Cloud Console.
        # 2. Run a script once to get user consent and store refresh token.
        # 3. Use the refresh token to get new access tokens in your automated script.
        # For this blueprint, we'll simulate the upload.

        # SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
        # flow = InstalledAppFlow.from_client_secrets_file("client_secrets.json", SCOPES)
        # credentials = flow.run_local_oauth2_flow(port=0) # Manual step for first time

        # Placeholder for actual YouTube API upload logic
        # youtube = build("youtube", "v3", credentials=credentials)
        # body = {
        #     "snippet": {
        #         "title": content.title,
        #         "description": content.body_html[:5000], # YouTube description limit
        #         "tags": content.keywords,
        #         "categoryId": "27", # Education category, adjust as needed
        #         "defaultLanguage": content.language
        #     },
        #     "status": {
        #         "privacyStatus": "public",
        #         "selfDeclaredMadeForKids": False,
        #     }
        # }
        # media_body = MediaFileUpload(content.associated_video_path, chunksize=-1, resumable=True)
        # request = youtube.videos().insert(part="snippet,status", body=body, media_body=media_body)
        # response = None
        # while response is None:
        #     status, response = request.next_chunk()
        #     if status:
        #         logger.info(f"Uploaded {int(status.resumable_progress * 100)}%")
        # final_response_data = response

        # Simulate success
        youtube_url = f"https://www.youtube.com/watch?v=AI_GEN_{generated_content_id}_{hashlib.md5(content.title.encode()).hexdigest()[:8]}"

        try:
            published_record = PublishedContent(
                generated_content_id=generated_content_id,
                platform="YOUTUBE",
                external_url=youtube_url
            )
            db_manager.insert_record(published_record)
            content.status = "PUBLISHED"  # Mark as published after all platforms are done, or manage per platform
            db_manager.update_record(content)
            logger.info(f"Successfully published video {generated_content_id} to YouTube: {youtube_url}")
            return youtube_url

        except Exception as e:  # Catch HttpError for API specific errors in real implementation
            logger.error(f"YouTube publishing failed for {generated_content_id}: {e}")
            content.status = "ERROR_PUBLISH"
            db_manager.update_record(content)
            return None

    # Implement similar methods for Twitter, Reddit, Pinterest publishing.
    # Each would require specific API client setup and error handling.
    # Be extremely cautious with automated posting to avoid platform bans.
    # Twitter/X API: https://developer.twitter.com/en/docs/api-reference-index
    # Reddit API: https://www.reddit.com/dev/api/
    # Pinterest API: https://developers.pinterest.com/docs/api/v5/
