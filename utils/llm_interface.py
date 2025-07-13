# utils/llm_interface.py
from google.generativeai import GenerativeModel, configure
from openai import OpenAI
from config.settings import GEMINI_API_KEY, OPENAI_API_KEY, TEXT_GENERATION_MODEL
from utils.logger import setup_logger

logger = setup_logger("LLM_Interface")


class LLMInterface:
    """
    Unified interface for interacting with various Large Language Models.
    Handles API configuration and basic error logging.
    """

    def __init__(self):
        self.gemini_model = None
        self.openai_client = None
        self.openai_model = "gpt-4o"  # Default OpenAI model

        # Configure Gemini
        if GEMINI_API_KEY:
            try:
                configure(api_key=GEMINI_API_KEY)
                self.gemini_model = GenerativeModel(TEXT_GENERATION_MODEL)
                logger.info(f"Gemini model '{TEXT_GENERATION_MODEL}' initialized.")
            except Exception as e:
                logger.error(f"Failed to configure Gemini API: {e}")
                self.gemini_model = None
        else:
            logger.warning("GEMINI_API_KEY not found. Gemini will not be available.")

        # Configure OpenAI
        if OPENAI_API_KEY:
            try:
                self.openai_client = OpenAI(api_key=OPENAI_API_KEY)
                logger.info(f"OpenAI client initialized with model '{self.openai_model}'.")
            except Exception as e:
                logger.error(f"Failed to configure OpenAI API: {e}")
                self.openai_client = None
        else:
            logger.warning("OPENAI_API_KEY not found. OpenAI will not be available.")

    def generate_text(self, prompt: str, temperature: float = 0.7, max_tokens: int = 2000,
                      model_choice: str = "gemini") -> str | None:
        """
        Generates text using the specified LLM.
        """
        try:
            if model_choice == "gemini" and self.gemini_model:
                response = self.gemini_model.generate_content(
                    prompt,
                    generation_config={"temperature": temperature, "max_output_tokens": max_tokens}
                )
                return response.text
            elif model_choice == "openai" and self.openai_client:
                response = self.openai_client.chat.completions.create(
                    model=self.openai_model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature,
                    max_tokens=max_tokens
                )
                return response.choices[0].message.content
            else:
                logger.error(f"LLM model '{model_choice}' not configured or invalid choice.")
                return None
        except Exception as e:
            logger.error(f"Error generating text with {model_choice}: {e}")
            return None

    def embed_text(self, text: str, model_choice: str = "gemini") -> list[float] | None:
        """
        Generates embeddings for text, used for similarity checks (deduplication).
        """
        try:
            if model_choice == "gemini" and self.gemini_model:
                response = self.gemini_model.embed_content(
                    model='models/embedding-001',  # Specific embedding model
                    content=text
                )
                return response['embedding']
            elif model_choice == "openai" and self.openai_client:
                response = self.openai_client.embeddings.create(
                    model="text-embedding-ada-002",  # Or newer embedding models
                    input=text
                )
                return response.data[0].embedding
            else:
                logger.error(f"Embedding model '{model_choice}' not configured or invalid choice.")
                return None
        except Exception as e:
            logger.error(f"Error generating embedding with {model_choice}: {e}")
            return None




