# database/db_manager.py
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine, text
from database.models import Base, RawIngestedData, StructuredFact, GeneratedContent, PublishedContent, PerformanceMetric
from config.settings import DATABASE_URL
from utils.logger import setup_logger
import hashlib

logger = setup_logger("DBManager")


class DBManager:
    """
    Manages all database interactions.
    Provides methods for CRUD operations and specific queries needed by agents.
    """

    def __init__(self):
        self.engine = create_engine(DATABASE_URL)
        # Ensure tables are created when DBManager is initialized
        try:
            Base.metadata.create_all(self.engine)
            logger.info("Database tables ensured to be created.")
        except Exception as e:
            logger.error(f"Failed to create database tables: {e}")
            raise  # Re-raise to halt if DB isn't ready

        self.Session = sessionmaker(bind=self.engine)

    def get_session(self):
        """Returns a new database session."""
        return self.Session()

    def insert_record(self, record_obj):
        """Inserts a new record into the database."""
        session = self.get_session()
        try:
            session.add(record_obj)
            session.commit()
            session.refresh(record_obj)  # Refresh to get auto-generated IDs
            logger.debug(f"Inserted: {record_obj}")
            return record_obj
        except Exception as e:
            session.rollback()
            logger.error(f"DB Insert Error for {record_obj.__class__.__name__}: {e}")
            return None
        finally:
            session.close()

    def update_record(self, record_obj):
        """Updates an existing record in the database."""
        session = self.get_session()
        try:
            session.merge(record_obj)  # Use merge for updating existing detached objects
            session.commit()
            logger.debug(f"Updated: {record_obj}")
            return record_obj
        except Exception as e:
            session.rollback()
            logger.error(f"DB Update Error for {record_obj.__class__.__name__}: {e}")
            return None
        finally:
            session.close()

    def query_records(self, model, **filters):
        """Queries records from a specified model with optional filters."""
        session = self.get_session()
        try:
            query = session.query(model)
            for key, value in filters.items():
                query = query.filter(getattr(model, key) == value)
            return query.all()
        except Exception as e:
            logger.error(f"DB Query Error for {model.__name__}: {e}")
            return []
        finally:
            session.close()

    def get_record_by_id(self, model, record_id):
        """Retrieves a record by its ID."""
        session = self.get_session()
        try:
            return session.query(model).get(record_id)
        except Exception as e:
            logger.error(f"DB Get by ID Error for {model.__name__} (ID: {record_id}): {e}")
            return None
        finally:
            session.close()

    def get_record_by_url(self, model, url_field, url):
        """Retrieves a record by a URL field."""
        session = self.get_session()
        try:
            return session.query(model).filter(getattr(model, url_field) == url).first()
        except Exception as e:
            logger.error(f"DB Get by URL Error for {model.__name__} (URL: {url}): {e}")
            return None
        finally:
            session.close()

    def is_raw_data_url_exists(self, url: str) -> bool:
        """Checks if a URL already exists in RawIngestedData."""
        session = self.get_session()
        try:
            return session.query(RawIngestedData).filter_by(url=url).first() is not None
        except Exception as e:
            logger.error(f"Error checking raw data URL existence: {e}")
            return False
        finally:
            session.close()

    def is_content_hash_exists(self, content_hash: str) -> bool:
        """Checks if a content hash already exists in GeneratedContent."""
        session = self.get_session()
        try:
            return session.query(GeneratedContent).filter_by(content_hash=content_hash).first() is not None
        except Exception as e:
            logger.error(f"Error checking content hash existence: {e}")
            return False
        finally:
            session.close()

    def is_embedding_hash_exists(self, embedding_hash: str) -> bool:
        """Checks if an embedding hash already exists in StructuredFact (for semantic deduplication)."""
        session = self.get_session()
        try:
            return session.query(StructuredFact).filter_by(embedding_hash=embedding_hash).first() is not None
        except Exception as e:
            logger.error(f"Error checking embedding hash existence: {e}")
            return False
        finally:
            session.close()

    def get_unprocessed_raw_data(self, limit: int = 50):
        """Retrieves a batch of raw data records that need parsing."""
        session = self.get_session()
        try:
            return session.query(RawIngestedData).filter_by(status="NEW").limit(limit).all()
        except Exception as e:
            logger.error(f"Error getting unprocessed raw data: {e}")
            return []
        finally:
            session.close()

    def get_structured_data_for_generation(self, limit: int = 10):
        """Retrieves structured facts that haven't been used for content generation yet."""
        session = self.get_session()
        try:
            # Order by timestamp to process older facts first
            return session.query(StructuredFact).filter_by(is_processed_for_content=False).order_by(
                StructuredFact.timestamp).limit(limit).all()
        except Exception as e:
            logger.error(f"Error getting structured data for generation: {e}")
            return []
        finally:
            session.close()

    def get_generated_content_for_monetization_or_publishing(self, limit: int = 5):
        """Retrieves content that is generated but not yet monetized/published."""
        session = self.get_session()
        try:
            return session.query(GeneratedContent).filter(
                GeneratedContent.status.in_(["GENERATED", "MONETIZED"])
                # Can be 'GENERATED' or 'MONETIZED' if monetization is separate from publishing
            ).limit(limit).all()
        except Exception as e:
            logger.error(f"Error getting content for monetization/publishing: {e}")
            return []
        finally:
            session.close()

    def get_published_content_for_metrics(self, limit: int = 100):
        """Retrieves published content records to collect performance metrics for."""
        session = self.get_session()
        try:
            # In a real system, you'd filter by last_metric_collection_date
            return session.query(PublishedContent).limit(limit).all()
        except Exception as e:
            logger.error(f"Error getting published content for metrics: {e}")
            return []
        finally:
            session.close()

