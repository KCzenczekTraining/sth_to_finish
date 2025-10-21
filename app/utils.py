"""
File handling utilities
"""

import aiofiles
import json
import logging
import mimetypes
import os
import uuid
import zipfile

from pathlib import Path
from typing import List, Optional, Set, Tuple
from fastapi import HTTPException, UploadFile


class FileConfig:
    """File handling configuration"""
    def __init__(self, 
                 supported_audio_types: Optional[Set[str]] = None,
                 max_file_size: int = 50 * 1024 * 1024,
                 logger_name: str = __name__):
        self.supported_audio_types = supported_audio_types or {
            'audio/mpeg',
            'audio/mp3'
        }
        self.max_file_size = max_file_size
        self.logger = logging.getLogger(logger_name)


# Default file configuration instance
_file_config = FileConfig()


def validate_audio_file(file: UploadFile, config: Optional[FileConfig] = None) -> Tuple[bool, str]:
    if config is None:
        config = _file_config
        
    if not file or not file.filename:
        return False, "No file provided"
    
    if hasattr(file, 'size') and file.size and file.size > config.max_file_size:
        return False, f"File too large (max {config.max_file_size // (1024*1024)}MB)"
    
    # Check MIME type
    content_type = file.content_type
    config.logger.debug(f"File content type: {content_type}")
    
    if content_type not in config.supported_audio_types:
        # Fallback: guess from filename extension
        guessed_type, _ = mimetypes.guess_type(file.filename)
        config.logger.debug(f"Guessed content type from filename: {guessed_type}")
        
        if guessed_type not in config.supported_audio_types:
            config.logger.warning(f"File validation failed: Unsupported file type {content_type}/{guessed_type}")
            return False, f"This is an unsupported file type. Supported types: {', '.join(sorted(config.supported_audio_types))}"
        content_type = guessed_type
    
    return True, content_type


def generate_unique_filename(original_filename: str) -> str:
    file_extension = Path(original_filename).suffix
    return f"{uuid.uuid4()}{file_extension}"


async def save_uploaded_file(file: UploadFile, filename: str, upload_dir: Path, config: Optional[FileConfig] = None) -> int:
    if config is None:
        config = _file_config
        
    file_path = upload_dir / filename
    file_size = 0
    
    try:
        async with aiofiles.open(file_path, 'wb') as f:
            # Reset file position to beginning
            await file.seek(0)
            
            # Read and write in chunks to handle large files
            chunk_size = 8192
            chunks_written = 0
            
            while chunk := await file.read(chunk_size):
                file_size += len(chunk)
                chunks_written += 1
                await f.write(chunk)
                
                # Log progress for large files
                if chunks_written % 100 == 0:
                    config.logger.debug(f"File save progress: {filename} - {file_size} bytes written")
                
                # Check file size limit during upload
                if file_size > config.max_file_size:
                    config.logger.error(f"File size limit exceeded during save: {filename} - {file_size} bytes")
                    # Clean up partial file
                    try:
                        os.unlink(file_path)
                        config.logger.info(f"Cleaned up partial file: {filename}")
                    except OSError as e:
                        config.logger.error(f"Failed to cleanup partial file {filename}: {e}")
                    raise HTTPException(
                        status_code=413,
                        detail=f"File size exceeds maximum allowed size of {config.max_file_size // (1024*1024)}MB"
                    )
        
        config.logger.info(f"File saved successfully: {filename} - {file_size} bytes")
    
    except Exception as e:
        config.logger.error(f"Error saving file {filename}: {str(e)}")
        # Clean up partial file on error
        try:
            if file_path.exists():
                os.unlink(file_path)
                config.logger.info(f"Cleaned up partial file after error: {filename}")
        except OSError as cleanup_error:
            config.logger.error(f"Failed to cleanup partial file {filename}: {cleanup_error}")
        raise e
    
    return file_size


async def create_zip_with_metadata(audio_files: List[dict], upload_dir: Path, temp_dir: Path, config: Optional[FileConfig] = None) -> str:
    if config is None:
        config = _file_config
        
    zip_filename = f"audio_export_{uuid.uuid4()}.zip"
    zip_path = temp_dir / zip_filename
    
    # Ensure temp directory exists
    temp_dir.mkdir(exist_ok=True)
    
    try:
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            files_added = 0
            files_missing = 0
            
            # Add audio files
            for file_info in audio_files:
                stored_filename = file_info.get('stored_filename')
                original_filename = file_info.get('original_filename')
                
                if stored_filename and original_filename:
                    audio_file_path = upload_dir / stored_filename
                    if audio_file_path.exists():
                        # Use original filename in the ZIP
                        zipf.write(audio_file_path, f"audio_files/{original_filename}")
                        files_added += 1
                        config.logger.debug(f"Added file to ZIP: {original_filename}")
                    else:
                        files_missing += 1
                        config.logger.warning(f"File not found for ZIP: {stored_filename} (original: {original_filename})")
                else:
                    files_missing += 1
                    config.logger.warning(f"Invalid file info for ZIP: {file_info}")
            
            config.logger.info(f"ZIP archive stats: {files_added} files added, {files_missing} files missing")
            
            # Create and add metadata file
            metadata_content = {
                "export_timestamp": "2024-01-01T00:00:00",  # Will be set properly in endpoint
                "total_files": len(audio_files),
                "files": audio_files
            }
            
            metadata_json = json.dumps(metadata_content, indent=2)
            zipf.writestr("metadata.json", metadata_json)
            config.logger.debug("Added metadata.json to ZIP archive")
        
        final_size = os.path.getsize(zip_path)
        config.logger.info(f"ZIP archive created successfully: {zip_filename} - {final_size} bytes")
    
    except Exception as e:
        config.logger.error(f"Error creating ZIP archive {zip_filename}: {str(e)}")
        # Clean up partial ZIP file on error
        try:
            if zip_path.exists():
                os.unlink(zip_path)
                config.logger.info(f"Cleaned up partial ZIP file: {zip_filename}")
        except OSError as cleanup_error:
            config.logger.error(f"Failed to cleanup partial ZIP file {zip_filename}: {cleanup_error}")
        raise e
    
    return str(zip_path)


def cleanup_temp_file(file_path: str, config: Optional[FileConfig] = None) -> None:
    if config is None:
        config = _file_config
        
    try:
        if os.path.exists(file_path):
            os.unlink(file_path)
    except OSError as e:
        config.logger.error(f"Failed to cleanup {file_path}: {e}")


def get_file_config() -> FileConfig:
    """Get file configuration instance for dependency injection"""
    return _file_config
