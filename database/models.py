# database/models.py
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Boolean, Float, JSON, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
from config.settings import DATABASE_URL

Base = declarative_base()


class RawIngestedData(Base):
    """
    Stores raw HTML/data scraped from external sources.
    """
    __tablename__ = 'raw_ingested_data'
    id = Column(Integer, primary_key=True, autoincrement=True)
    url = Column(String, unique=True, nullable=False)
    raw_html = Column(Text, nullable=False)
    extracted_json = Column(JSON, nullable=True)  # Initial data extracted by scraper
    timestamp = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default="NEW")  # NEW, PARSED, FAILED_PARSING, DUPLICATE_PARSED

    def __repr__(self):
        return f"<RawIngestedData(id={self.id}, url='{self.url}', status='{self.status}')>"


class StructuredFact(Base):
    """
    Stores structured, normalized facts extracted from raw data.
    Used as input for content generation.
    """
    __tablename__ = 'structured_facts'
    id = Column(Integer, primary_key=True, autoincrement=True)
    source_url = Column(String, nullable=False)
    niche_category = Column(String, nullable=False)  # e.g., "Solar Pump Troubleshooting", "Gov Scheme Eligibility"
    language = Column(String, nullable=False)  # Language of the original source/intended target
    data = Column(JSON, nullable=False)  # Generic JSON field to store varying structured data based on niche_category
    embedding = Column(JSON, nullable=True)  # Vector embedding for semantic deduplication
    embedding_hash = Column(String, unique=True, nullable=True)  # Simple hash of embedding for quick check
    timestamp = Column(DateTime, default=datetime.utcnow)
    is_processed_for_content = Column(Boolean, default=False)  # True if content has been generated from this fact

    def __repr__(self):
        return f"<StructuredFact(id={self.id}, category='{self.niche_category}', processed={self.is_processed_for_content})>"


class GeneratedContent(Base):
    """
    Stores the AI-generated content before publishing.
    """
    __tablename__ = 'generated_content'
    id = Column(Integer, primary_key=True, autoincrement=True)
    content_hash = Column(String, unique=True, nullable=False)  # MD5 hash of content to prevent exact duplicates
    title = Column(String, nullable=False)
    body_html = Column(Text, nullable=False)  # Can be Markdown which is converted to HTML for publishing
    language = Column(String, nullable=False)
    content_type = Column(String, nullable=False)  # e.g., "ARTICLE", "GUIDE", "FAQ", "VIDEO_SCRIPT"
    keywords = Column(JSON, nullable=True)  # List of keywords used for generation/SEO
    associated_images = Column(JSON, nullable=True)  # List of local paths to generated images
    associated_video_path = Column(String, nullable=True)  # Local path to generated video file
    meta_data = Column(JSON, nullable=True)  # SEO meta title, description, internal link suggestions
    timestamp = Column(DateTime, default=datetime.utcnow)
    status = Column(String,
                    default="GENERATED")  # GENERATED, MONETIZED, PUBLISHED, ERROR_GENERATION, ERROR_MONETIZATION, ERROR_PUBLISH

    published_records = relationship("PublishedContent", back_populates="generated_content")

    def __repr__(self):
        return f"<GeneratedContent(id={self.id}, title='{self.title[:30]}...', status='{self.status}')>"


class PublishedContent(Base):
    """
    Records details of content published to external platforms.
    """
    __tablename__ = 'published_content'
    id = Column(Integer, primary_key=True, autoincrement=True)
    generated_content_id = Column(Integer, ForeignKey('generated_content.id'), nullable=False)
    platform = Column(String, nullable=False)  # e.g., "WORDPRESS", "YOUTUBE", "TWITTER"
    external_url = Column(String, unique=True, nullable=False)
    publish_date = Column(DateTime, default=datetime.utcnow)

    generated_content = relationship("GeneratedContent", back_populates="published_records")
    performance_metrics = relationship("PerformanceMetric", back_populates="published_content")

    def __repr__(self):
        return f"<PublishedContent(id={self.id}, platform='{self.platform}', url='{self.external_url}')>"


class PerformanceMetric(Base):
    """
    Stores performance data collected from analytics and ad platforms.
    """
    __tablename__ = 'performance_metrics'
    id = Column(Integer, primary_key=True, autoincrement=True)
    published_content_id = Column(Integer, ForeignKey('published_content.id'), nullable=False)
    metric_type = Column(String, nullable=False)  # e.g., "VIEWS", "CLICKS", "REVENUE_USD", "BOUNCE_RATE"
    value = Column(Float, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

    published_content = relationship("PublishedContent", back_populates="performance_metrics")

    def __repr__(self):
        return f"<PerformanceMetric(id={self.id}, type='{self.metric_type}', value={self.value})>"


