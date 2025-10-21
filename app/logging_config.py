"""
Logging configuration
"""

import logging
import logging.handlers

from pathlib import Path


class LoggingConfig:
    """Logging configuration and management"""
    def __init__(self, logs_dir: str = "logs"):
        self.logs_dir = Path(logs_dir)
        self.logs_dir.mkdir(exist_ok=True)
        self.app_log_file = self.logs_dir / "audio_server.log"
        self.error_log_file = self.logs_dir / "audio_server_errors.log"
        self.access_log_file = self.logs_dir / "audio_server_access.log"
    
    def setup_logging(self):
        """Setup logging configuration"""
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)
        
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        formatter = logging.Formatter(
            fmt='%(asctime)s | %(name)s | %(levelname)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
        
        app_handler = logging.handlers.RotatingFileHandler(
            self.app_log_file,
            maxBytes=10*1024*1024,
            backupCount=5,
            encoding='utf-8'
        )
        app_handler.setLevel(logging.DEBUG)
        app_handler.setFormatter(formatter)
        root_logger.addHandler(app_handler)
        
        error_handler = logging.handlers.RotatingFileHandler(
            self.error_log_file,
            maxBytes=5*1024*1024,
            backupCount=3,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(formatter)
        root_logger.addHandler(error_handler)
        
        access_logger = logging.getLogger("access")
        access_logger.setLevel(logging.INFO)
        access_logger.propagate = False
        
        access_handler = logging.handlers.RotatingFileHandler(
            self.access_log_file,
            maxBytes=10*1024*1024,
            backupCount=5,
            encoding='utf-8'
        )
        access_formatter = logging.Formatter(
            fmt='%(asctime)s | ACCESS | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        access_handler.setFormatter(access_formatter)
        access_logger.addHandler(access_handler)
        
        return root_logger


# Default logging configuration instance
_logging_config = LoggingConfig()


def setup_logging():
    """Setup logging using default configuration - for backward compatibility"""
    return _logging_config.setup_logging()


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def get_logging_config() -> LoggingConfig:
    """Get logging configuration instance for dependency injection"""
    return _logging_config


def log_api_access(method: str, path: str, user_id: str = None, status_code: int = None, 
                   response_time: float = None, file_size: int = None, error: str = None):
    access_logger = logging.getLogger("access")
    
    log_parts = [
        f"method={method}",
        f"path={path}",
        f"user_id={user_id or 'anonymous'}",
        f"status={status_code or 'N/A'}",
    ]
    
    if response_time is not None:
        log_parts.append(f"response_time={response_time:.3f}s")
    
    if file_size is not None:
        log_parts.append(f"file_size={file_size}bytes")
    
    if error:
        log_parts.append(f"error={error}")
    
    access_logger.info(" | ".join(log_parts))


def log_file_operation(operation: str, filename: str, user_id: str, success: bool, 
                      file_size: int = None, error: str = None):
    logger = logging.getLogger("file_ops")
    
    log_parts = [
        f"operation={operation}",
        f"filename={filename}",
        f"user_id={user_id}",
        f"success={success}",
    ]
    
    if file_size is not None:
        log_parts.append(f"size={file_size}bytes")
    
    if error:
        log_parts.append(f"error={error}")
    
    message = " | ".join(log_parts)
    
    if success:
        logger.info(message)
    else:
        logger.error(message)


def log_database_operation(operation: str, table: str, record_id: str = None, 
                          success: bool = True, error: str = None):
    logger = logging.getLogger("database")
    
    log_parts = [
        f"operation={operation}",
        f"table={table}",
        f"record_id={record_id or 'N/A'}",
        f"success={success}",
    ]
    
    if error:
        log_parts.append(f"error={error}")
    
    message = " | ".join(log_parts)
    
    if success:
        logger.info(message)
    else:
        logger.error(message)
