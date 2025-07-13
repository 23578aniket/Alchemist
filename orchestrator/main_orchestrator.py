# orchestrator/main_orchestrator.py
from celery import Celery
from celery.schedules import crontab  # For more advanced scheduling like daily at specific time
from config.settings import CELERY_BROKER_URL, CELERY_RESULT_BACKEND, NICHE_TOPIC, TARGET_LANGUAGES, \
    CONTENT_VOLUME_PER_DAY
from utils.logger import setup_logger
from database.db_manager import DBManager
from database.models import RawIngestedData, StructuredFact, GeneratedContent
from agents.data_ingestion import DataIngestionAgent
from agents.content_generation import ContentGenerationAgent
from agents.seo_distribution import SEODistributionAgent
from agents.monetization_feedback import MonetizationFeedbackAgent
import time
import random

logger = setup_logger("Orchestrator")
db_manager = DBManager()

# Initialize Celery app
app = Celery('autonomous_alchemist', broker=CELERY_BROKER_URL, backend=CELERY_RESULT_BACKEND)
app.conf.broker_connection_retry_on_startup = True
app.conf.timezone = 'Asia/Kolkata'  # India Standard Time

# Initialize Agent instances (Celery tasks will create their own instances or pass necessary data)
# For simplicity in blueprint, we'll initialize them globally, but in production,
# tasks might instantiate them or use dependency injection.
data_ingestion_agent = DataIngestionAgent()
content_generation_agent = ContentGenerationAgent()
seo_distribution_agent = SEODistributionAgent()
monetization_feedback_agent = MonetizationFeedbackAgent()


# --- Celery Tasks (The Automated Workflow) ---

@app.task(bind=True, max_retries=3, default_retry_delay=300)  # Retry after 5 minutes
def scrape_url_task(self, url: str) -> None:
    """Task to scrape a single URL and ingest raw data."""
    logger.info(f"Task: Scraping URL {url}")
    try:
        raw_data_id = data_ingestion_agent.scrape_url(url)
        if raw_data_id:
            # Chain to parsing task if scrape was successful
            process_raw_data_task.delay(raw_data_id)
    except Exception as e:
        logger.error(f"Scrape task failed for {url}: {e}")
        raise self.retry(exc=e)  # Retry the task on failure


@app.task(bind=True, max_retries=3, default_retry_delay=300)
def process_raw_data_task(self, raw_data_id: int) -> None:
    """Task to parse and filter raw data into structured facts."""
    logger.info(f"Task: Processing raw data ID {raw_data_id}")
    try:
        structured_fact_id = data_ingestion_agent.process_raw_data(raw_data_id)
        if structured_fact_id:
            logger.info(f"Structured fact created: {structured_fact_id}. Ready for content generation.")
    except Exception as e:
        logger.error(f"Processing raw data task failed for ID {raw_data_id}: {e}")
        raise self.retry(exc=e)


@app.task(bind=True, max_retries=3, default_retry_delay=600)  # Longer delay for content generation
def generate_content_pipeline_task(self, structured_fact_id: int, language: str,
                                   keywords: list[str] | None = None) -> None:
    """
    Main content generation pipeline: article -> images -> video (optional) -> monetization -> SEO -> publish.
    """
    logger.info(f"Task: Starting content generation pipeline for structured fact ID {structured_fact_id} in {language}")
    try:
        # 1. Generate Article
        generated_content_id = content_generation_agent.generate_article(structured_fact_id, language, keywords)
        if not generated_content_id:
            logger.warning(f"Skipping pipeline for {structured_fact_id} as article generation failed or was duplicate.")
            return

        # 2. Generate Images
        image_paths = content_generation_agent.generate_images_for_content(generated_content_id)
        if not image_paths:
            logger.warning(f"No images generated for content ID {generated_content_id}.")

        # 3. Generate Video (Optional, if video is part of strategy)
        video_path = content_generation_agent.generate_video_for_content(generated_content_id)
        if video_path:
            logger.info(f"Video generated for content ID {generated_content_id} at {video_path}")
        else:
            logger.warning(f"No video generated for content ID {generated_content_id}.")

        # 4. Inject Monetization
        monetization_feedback_agent.inject_monetization(generated_content_id)

        # 5. Optimize SEO
        seo_data = seo_distribution_agent.optimize_content_seo(generated_content_id)
        if not seo_data:
            logger.warning(f"SEO optimization failed for content ID {generated_content_id}.")

        # 6. Publish to Platforms
        wordpress_url = seo_distribution_agent.publish_to_wordpress(generated_content_id)
        if wordpress_url:
            logger.info(f"Content {generated_content_id} published to WordPress: {wordpress_url}")
        else:
            logger.error(f"Failed to publish content {generated_content_id} to WordPress.")

        if video_path:  # Only attempt YouTube publish if video was actually generated
            youtube_url = seo_distribution_agent.publish_to_youtube(generated_content_id)
            if youtube_url:
                logger.info(f"Content {generated_content_id} published to YouTube: {youtube_url}")
            else:
                logger.error(f"Failed to publish video {generated_content_id} to YouTube.")

        # You can add more publishing platforms here (Twitter, Facebook, etc.)
        # e.g., seo_distribution_agent.publish_to_twitter(generated_content_id)

    except Exception as e:
        logger.error(f"Content generation pipeline failed for structured fact ID {structured_fact_id}: {e}")
        raise self.retry(exc=e)


@app.task(bind=True, max_retries=3, default_retry_delay=3600)  # Retry after 1 hour
def collect_and_analyze_metrics_task(self) -> None:
    """Task to collect performance metrics and analyze for optimization."""
    logger.info("Task: Collecting and analyzing performance metrics.")
    try:
        monetization_feedback_agent.collect_performance_metrics()
        monetization_feedback_agent.analyze_and_optimize()
    except Exception as e:
        logger.error(f"Metrics collection/analysis task failed: {e}")
        raise self.retry(exc=e)


# --- Orchestrator Scheduling (Celery Beat Configuration) ---
# This dictionary defines how often tasks run. Celery Beat process uses this.
app.conf.beat_schedule = {
    'scrape-new-data-sources-daily': {
        'task': 'orchestrator.main_orchestrator.discover_and_queue_scrape_targets_task',
        'schedule': crontab(hour=2, minute=0),  # Every day at 2:00 AM IST
        'args': ([  # Initial seed URLs for scraping
                     {"url": "https://agri.rajasthan.gov.in/content/agriculture/en/schemes.html",
                      "selectors": {"scheme_name": ".scheme-title", "scheme_details": ".scheme-description"}},
                     {"url": "https://www.solarcompaniesindia.com/solar-pump-manufacturers-rajasthan",
                      "selectors": {"company_name": ".company-name", "pump_models": ".pump-model-list"}},
                     # Add more initial, high-value, niche-specific URLs here.
                     # These are just examples. Real URLs need to be carefully selected.
                     {"url": "https://rajasthan.gov.in/solar-energy-policy", "selectors": {"policy_details": "body"}},
                     {"url": "https://pmkusum.mnre.gov.in/", "selectors": {"scheme_info": "body"}}
                 ],)
    },
    'process-unparsed-data-every-3-hours': {
        'task': 'orchestrator.main_orchestrator.process_all_unparsed_data_task',
        'schedule': timedelta(hours=3),
    },
    'trigger-content-generation-hourly': {
        'task': 'orchestrator.main_orchestrator.trigger_content_generation_task',
        'schedule': timedelta(hours=1),  # Attempt to generate new content every hour
    },
    'collect-and-analyze-metrics-daily': {
        'task': 'orchestrator.main_orchestrator.collect_and_analyze_metrics_task',
        'schedule': crontab(hour=4, minute=30),  # Every day at 4:30 AM IST
    },
}


# --- Orchestrator Helper Tasks (called by Celery Beat) ---

@app.task
def discover_and_queue_scrape_targets_task(initial_urls: list[dict]) -> None:
    """
    Discovers new URLs to scrape based on niche and queues them.
    This is where the system would autonomously expand its data sources.
    """
    logger.info("Task: Discovering and queuing new data sources for scraping.")

    # In a real system, this would involve:
    # 1. Using LLM to generate search queries based on NICHE_TOPIC and existing high-performing keywords.
    #    E.g., prompt = f"Generate 10 Google search queries for '{NICHE_TOPIC}' in {language} focusing on 'troubleshooting', 'maintenance', 'subsidies'."
    # 2. Using a Search API (e.g., Google Custom Search API, SerpAPI) to get search results.
    # 3. Filtering search results for relevant domains/URLs.
    # 4. Adding new, unique URLs to a queue for `scrape_url_task`.

    # For this blueprint, we'll just re-queue the initial URLs to ensure continuous data flow.
    # In a real scenario, you'd have logic to find *new* URLs dynamically.
    for target in initial_urls:
        scrape_url_task.delay(target["url"])  # No specific selectors needed here, scraper will try to extract broadly
        time.sleep(random.uniform(0.5, 2.0))  # Introduce random delay


@app.task
def process_all_unparsed_data_task() -> None:
    """Processes all raw data records that are in 'NEW' status."""
    logger.info("Task: Processing all unprocessed raw data records.")
    unprocessed_records = db_manager.get_unprocessed_raw_data(limit=50)  # Process a batch
    if not unprocessed_records:
        logger.info("No new raw data records to process.")
        return

    for record in unprocessed_records:
        process_raw_data_task.delay(record.id)
        time.sleep(random.uniform(0.1, 0.5))  # Small delay between tasks


@app.task
def trigger_content_generation_task() -> None:
    """
    Triggers content generation for available structured facts.
    Prioritizes facts not yet processed for content.
    """
    logger.info("Task: Triggering content generation pipeline for available structured facts.")
    structured_facts = db_manager.get_structured_data_for_generation(
        limit=CONTENT_VOLUME_PER_DAY)  # Get a batch for daily volume

    if not structured_facts:
        logger.info("No new structured facts available for content generation.")
        return

    for fact in structured_facts:
        # Determine target language and keywords.
        # For blueprint, use the language from the structured fact, and generic keywords.
        # In a real system, keywords would come from SEO agent analysis.
        target_lang = fact.language if fact.language in TARGET_LANGUAGES else "en"  # Fallback to English

        # Example keywords derived from structured data (can be enhanced by SEO agent)
        keywords = [NICHE_TOPIC, fact.data.get("pump_model", ""), fact.data.get("gov_schemes", [{}])[0].get("name", "")]
        keywords = [k for k in keywords if k]  # Remove empty strings

        generate_content_pipeline_task.delay(fact.id, target_lang, keywords)
        time.sleep(random.uniform(1, 5))  # Introduce random delay to space out LLM calls

