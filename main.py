# main.py
import os
from database.db_manager import DBManager
from utils.logger import setup_logger
from orchestrator.main_orchestrator import app  # Import the Celery app instance

logger = setup_logger("MainApp")


def initialize_database():
    """Initializes the database, ensuring tables are created."""
    logger.info("Initializing database...")
    try:
        db_manager = DBManager()
        # The DBManager constructor already calls Base.metadata.create_all()
        logger.info("Database initialized and tables ensured.")
    except Exception as e:
        logger.critical(f"Failed to initialize database: {e}. Exiting.")
        exit(1)


if __name__ == "__main__":
    # Ensure .env file exists for configuration
    if not os.path.exists(".env"):
        logger.critical(
            "ERROR: .env file not found. Please create one in the project root with all API keys and DB credentials as per config/settings.py.")
        exit(1)

    initialize_database()

    logger.info("Autonomous Digital Alchemist system setup complete.")
    logger.info("To start the system, run the following commands in separate terminal sessions:")
    logger.info("1. Start Redis (if not already running): `redis-server`")
    logger.info(
        "2. Start PostgreSQL (if not using docker-compose for DB): `pg_ctl -D /path/to/your/db/data -l logfile start`")
    logger.info("3. Start Celery Worker: `celery -A orchestrator.main_orchestrator worker -l info`")
    logger.info("4. Start Celery Beat (scheduler): `celery -A orchestrator.main_orchestrator beat -l info`")
    logger.info("\nAlternatively, use Docker Compose for a fully containerized setup:")
    logger.info("`docker-compose up --build -d`")
    logger.info("Monitor logs with: `docker-compose logs -f`")

