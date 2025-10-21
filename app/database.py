"""
Database models and config
"""

import json

from datetime import datetime
from typing import List, Optional
from sqlalchemy import Column, DateTime, Integer, String, Text, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session


class DatabaseConfig:
    """Database configuration and connection management"""
    def __init__(self, database_url: str = "sqlite:///./audio_metadata.db", echo: bool = False):
        self.database_url = database_url
        self.engine = create_engine(
            database_url,
            connect_args={"check_same_thread": False},
            echo=echo
        )
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.Base = declarative_base()
    
    def get_db_session(self):
        """Get database session with proper cleanup"""
        db = self.SessionLocal()
        try:
            yield db
        finally:
            db.close()
    
    def create_tables(self):
        """Create all database tables"""
        self.Base.metadata.create_all(bind=self.engine)


# Default database configuration instance
_db_config = DatabaseConfig()

# Export for backward compatibility
Base = _db_config.Base
engine = _db_config.engine


class AudioFile(Base):
    __tablename__ = "audio_files"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, nullable=False, index=True)
    original_filename = Column(String, nullable=False)
    stored_filename = Column(String, nullable=False)
    file_size = Column(Integer, nullable=False)
    mime_type = Column(String, nullable=False)
    tags = Column(Text, nullable=False, default="[]")
    additional_info = Column(Text, nullable=True)
    upload_timestamp = Column(DateTime, default=datetime.utcnow)

    def get_tags(self) -> List[str]:
        try:
            return json.loads(self.tags)
        except (json.JSONDecodeError, TypeError):
            return []

    def set_tags(self, tags: List[str]) -> None:
        self.tags = json.dumps(tags)

    def get_additional_info(self) -> Optional[dict]:
        if not self.additional_info:
            return None
        try:
            return json.loads(self.additional_info)
        except (json.JSONDecodeError, TypeError):
            return None

    def set_additional_info(self, metadata: Optional[dict]) -> None:
        if metadata is None:
            self.additional_info = None
        else:
            self.additional_info = json.dumps(metadata)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "original_filename": self.original_filename,
            "file_size": self.file_size,
            "mime_type": self.mime_type,
            "tags": self.get_tags(),
            "additional_info": self.get_additional_info(),
            "upload_timestamp": self.upload_timestamp.isoformat() if self.upload_timestamp else None
        }


def get_db():
    """Get database session - uses default config for backward compatibility"""
    yield from _db_config.get_db_session()


def get_db_config() -> DatabaseConfig:
    """Get database configuration instance for dependency injection"""
    return _db_config
