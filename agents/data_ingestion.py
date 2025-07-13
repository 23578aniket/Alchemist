# agents/data_ingestion.py
import requests
import json
import hashlib
import numpy as np  # For embedding operations
from bs4 import BeautifulSoup  # For basic HTML parsing
from config.settings import NICHE_TOPIC, NICHE_SCHEMA_PROMPT_SOLAR_PUMP_RAJA, BRIGHT_DATA_API_KEY, BRIGHT_DATA_HOST, \
    BRIGHT_DATA_PORT, BRIGHT_DATA_ZONE
from database.db_manager import DBManager
from database.models import RawIngestedData, StructuredFact
from utils.logger import setup_logger
from utils.llm_interface import LLMInterface
from urllib.parse import urlparse

logger = setup_logger("DataIngestionAgent")
db_manager = DBManager()
llm_interface = LLMInterface()


class DataIngestionAgent:
    """
    Agent responsible for scraping raw data and transforming it into structured facts.
    """

    def __init__(self):
        # Bright Data proxy setup
        self.proxy_host = BRIGHT_DATA_HOST
        self.proxy_port = BRIGHT_DATA_PORT
        self.proxy_user = f"brd-customer-{BRIGHT_DATA_API_KEY}-zone-{BRIGHT_DATA_ZONE}"
        self.proxy_pass = BRIGHT_DATA_API_KEY
        self.proxies = {
            "http": f"http://{self.proxy_user}:{self.proxy_pass}@{self.proxy_host}:{self.proxy_port}",
            "https": f"http://{self.proxy_user}:{self.proxy_pass}@{self.proxy_host}:{self.proxy_port}"
        }
        self.session = requests.Session()
        self.session.proxies = self.proxies

    def scrape_url(self, url: str) -> int | None:
        """
        Scrapes a given URL using a proxy and stores the raw HTML.
        Returns the ID of the RawIngestedData record, or None on failure.
        """
        if db_manager.is_raw_data_url_exists(url):
            logger.info(f"URL already exists in raw data: {url}. Skipping scrape.")
            return None

        logger.info(f"Attempting to scrape: {url}")
        try:
            # Use requests_html for JS rendering if needed, or a dedicated scraping API like Bright Data's Web Unlocker.
            # For simplicity, using basic requests with proxy.
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.88 Safari/537.36'
            }
            response = self.session.get(url, headers=headers, timeout=30)
            response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)

            raw_html = response.text

            raw_record = RawIngestedData(url=url, raw_html=raw_html, status="NEW")
            inserted_record = db_manager.insert_record(raw_record)
            if inserted_record:
                logger.info(f"Successfully scraped and saved raw data for {url}. ID: {inserted_record.id}")
                return inserted_record.id
            else:
                logger.error(f"Failed to save raw data for {url} to DB.")
                return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Scraping failed for {url} due to network/API error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error during scraping for {url}: {e}")
        return None

    def process_raw_data(self, raw_data_id: int) -> int | None:
        """
        Takes raw ingested data, parses and filters it using LLM,
        and stores as structured facts.
        Returns the ID of the StructuredFact record, or None on failure/duplicate.
        """
        raw_record = db_manager.get_record_by_id(RawIngestedData, raw_data_id)
        if not raw_record:
            logger.error(f"Raw data record {raw_data_id} not found for processing.")
            return None

        logger.info(f"Processing raw data from {raw_record.url}")

        # Extract main content from HTML using BeautifulSoup to reduce noise for LLM
        soup = BeautifulSoup(raw_record.raw_html, 'html.parser')
        # Try to find main content area, e.g., <article>, <main>, or div with specific class
        main_content_tag = soup.find('article') or soup.find('main') or soup.find('div', class_='main-content')
        text_content = main_content_tag.get_text(separator='\n', strip=True) if main_content_tag else soup.get_text(
            separator='\n', strip=True)

        # Limit input to LLM token window (e.g., 15,000 characters for Gemini Pro)
        llm_input_text = text_content[:15000]

        prompt = f"""You are an expert in agricultural technology and government schemes in Rajasthan.
        Extract the following structured information from the provided text, focusing specifically on small-scale solar pump systems, their maintenance, troubleshooting, and relevant government schemes for farmers in Rajasthan.

        **Niche Schema:**
        {NICHE_SCHEMA_PROMPT_SOLAR_PUMP_RAJA}

        **Raw Text Content:**
        {llm_input_text}

        Return the extracted data as a single JSON object. If a field is not found, omit that field from the JSON.
        """

        extracted_json_str = llm_interface.generate_text(prompt, model_choice="gemini", max_tokens=2000,
                                                         temperature=0.2)

        if not extracted_json_str:
            logger.error(f"Failed to extract structured data for {raw_record.url}. LLM response empty.")
            raw_record.status = "FAILED_PARSING"
            db_manager.update_record(raw_record)
            return None

        try:
            structured_data = json.loads(extracted_json_str)
            if not structured_data:
                raise ValueError("LLM returned empty JSON object.")

            # Generate embedding for semantic deduplication
            data_text_for_embedding = json.dumps(structured_data, sort_keys=True, ensure_ascii=False)
            data_embedding = llm_interface.embed_text(data_text_for_embedding)

            if data_embedding is None:
                logger.error(f"Failed to generate embedding for structured data from {raw_record.url}.")
                raw_record.status = "FAILED_EMBEDDING"
                db_manager.update_record(raw_record)
                return None

            # Simple hash of embedding for quick lookup. For true semantic deduplication,
            # you'd need a vector database (e.g., pgvector, Pinecone, Milvus) and similarity search.
            embedding_hash = hashlib.md5(np.array(data_embedding).tobytes()).hexdigest()

            if db_manager.is_embedding_hash_exists(embedding_hash):
                logger.info(
                    f"Structured data from {raw_record.url} is semantically similar (embedding hash). Skipping.")
                raw_record.status = "DUPLICATE_PARSED"
                db_manager.update_record(raw_record)
                return None

            # Determine language of the extracted data (can be refined with language detection libraries)
            # For now, assume based on content if it's Hindi or English
            extracted_lang = "hi" if "योजना" in json.dumps(structured_data, ensure_ascii=False) else "en"

            structured_fact = StructuredFact(
                source_url=raw_record.url,
                niche_category=NICHE_TOPIC,
                language=extracted_lang,
                data=structured_data,
                embedding=data_embedding,
                embedding_hash=embedding_hash,
                is_processed_for_content=False
            )
            inserted_fact = db_manager.insert_record(structured_fact)

            if inserted_fact:
                raw_record.status = "PARSED"
                db_manager.update_record(raw_record)
                logger.info(
                    f"Successfully processed raw data and saved structured facts for {raw_record.url}. Fact ID: {inserted_fact.id}")
                return inserted_fact.id
            else:
                logger.error(f"Failed to save structured fact for {raw_record.url} to DB.")
                return None

        except json.JSONDecodeError as e:
            logger.error(f"LLM output was not valid JSON for {raw_record.url}: {e} -> {extracted_json_str[:500]}")
            raw_record.status = "FAILED_JSON"
            db_manager.update_record(raw_record)
            return None
        except Exception as e:
            logger.error(f"Error during structured data processing for {raw_record.url}: {e}")
            raw_record.status = "FAILED_PARSING"
            db_manager.update_record(raw_record)
            return None

