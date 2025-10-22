from pathlib import Path

from .database import get_db_config
from .logging_config import get_logger, get_logging_config
from .utils import get_file_config

class AppConfig:
    def __init__(self):
        self.upload_dir = Path("audio_uploads")
        self.temp_dir = Path("temp_downloads")
        self.upload_dir.mkdir(exist_ok=True)
        self.temp_dir.mkdir(exist_ok=True)
        
        self.logging_config = get_logging_config()
        self.db_config = get_db_config()
        self.file_config = get_file_config()
        
        self.logging_config.setup_logging()
        self.logger = get_logger(__name__)
        self.db_config.create_tables()

_app_config = None

def get_app_config() -> AppConfig:
    global _app_config
    if _app_config is None:
        _app_config = AppConfig()
    return _app_config