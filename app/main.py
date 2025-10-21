"""
Main application file for Audio Server API
"""

import json
import os
import tempfile
import time
import uuid
import zipfile

from datetime import datetime
from pathlib import Path
from sqlalchemy.orm import Session
from typing import Dict, Optional
from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile
)
from fastapi.responses import FileResponse

from .database import AudioFile, Base, engine, get_db, get_db_config, DatabaseConfig
from .logging_config import (
    get_logger,
    get_logging_config,
    log_api_access,
    log_database_operation,
    log_file_operation,
    setup_logging,
    LoggingConfig
)
from .models import AudioFileResponse, ListResponse, UploadResponse
from .utils import (
    cleanup_temp_file,
    create_zip_with_metadata,
    generate_unique_filename,
    get_file_config,
    save_uploaded_file,
    validate_audio_file,
    FileConfig
)


# Initialize FastAPI app
app = FastAPI(title="Audio Server", version="1.0.0")


class AppConfig:
    """Application configuration settings"""
    def __init__(self):
        self.upload_dir = Path("audio_uploads")
        self.temp_dir = Path("temp_downloads")
        self.upload_dir.mkdir(exist_ok=True)
        self.temp_dir.mkdir(exist_ok=True)
        
        # Initialize sub-configurations
        self.logging_config = get_logging_config()
        self.db_config = get_db_config()
        self.file_config = get_file_config()
        
        # Setup logging
        self.logging_config.setup_logging()
        self.logger = get_logger(__name__)
        
        # Create database tables
        self.db_config.create_tables()


_app_config = AppConfig()


@app.on_event("startup")
async def startup_event():
    _app_config.logger.info(f"Server starting up at {datetime.now().isoformat()}")


@app.on_event("shutdown")
async def shutdown_event():
    _app_config.logger.info(f"Server shutting down at {datetime.now().isoformat()}")


def get_app_config() -> AppConfig:
    return _app_config


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Middleware to log all HTTP requests and responses."""
    start_time = time.time()
    
    # Extract user_id from query params or form data if available
    user_id = None
    if "user_id" in request.query_params:
        user_id = request.query_params["user_id"]
    
    # Basic request logging
    
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        
        log_api_access(request.method, request.url.path, user_id, response.status_code, process_time)
        return response
        
    except Exception as e:
        process_time = time.time() - start_time
        
        log_api_access(
            method=request.method,
            path=request.url.path,
            user_id=user_id,
            status_code=500,
            response_time=process_time,
            error=str(e)
        )
        
        _app_config.logger.error(f"Request failed: {request.method} {request.url.path} - Error: {str(e)} - Time: {process_time:.3f}s")
        raise


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.post("/upload", response_model=UploadResponse)
async def upload_audio(
    user_id: str = Form(..., description="ID of the user uploading the file"),
    tags: str = Form(default="", description="Comma-separated list of tags for the audio file"),
    additional_info: str = Form(default="", description="Additional information about the audio file"),
    audio: UploadFile = File(..., description="The audio file to upload"),
    db: Session = Depends(get_db),
    config: AppConfig = Depends(get_app_config)
) -> UploadResponse:
    """
    Upload an audio file with optional metadata.
    """
    
    logger = config.logger
    
    # Parse input data
    parsed_tags = [tag.strip() for tag in tags.split(",") if tag.strip()] if tags else []
    parsed_additional_info = additional_info.strip()
    
    # Validate and process audio file
    is_valid, mime_type_or_error = validate_audio_file(audio, config.file_config)
    if not is_valid:
        raise HTTPException(status_code=400, detail=mime_type_or_error)
    
    mime_type = mime_type_or_error
    unique_filename = generate_unique_filename(audio.filename)
    file_id = str(uuid.uuid4())
    
    # Save file
    try:
        file_size = await save_uploaded_file(audio, unique_filename, config.upload_dir, config.file_config)
        log_file_operation("upload", audio.filename, user_id, True, file_size)
    except Exception as e:
        log_file_operation("upload", audio.filename, user_id, False, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")
    
    # Create database record
    try:
        audio_record = AudioFile(
            id=file_id,
            user_id=user_id.strip(),
            original_filename=audio.filename,
            stored_filename=unique_filename,
            file_size=file_size,
            mime_type=mime_type,
            upload_timestamp=datetime.utcnow()
        )
        
        audio_record.set_tags(parsed_tags)
        if parsed_additional_info:
            audio_record.set_additional_info({"info": parsed_additional_info})
        
        db.add(audio_record)
        db.commit()
        db.refresh(audio_record)
        
        log_database_operation("insert", "audio_files", file_id, True)
        
        return UploadResponse(
            status="success",
            message="File uploaded successfully",
            file_id=file_id,
            file_info=AudioFileResponse(**audio_record.to_dict())
        )
        
    except Exception as e:
        db.rollback()
        log_database_operation("insert", "audio_files", file_id, False, str(e))
        
        # Cleanup file on database error
        file_path = config.upload_dir / unique_filename
        if file_path.exists():
            file_path.unlink()
        
        raise HTTPException(status_code=500, detail=f"Failed to save metadata: {str(e)}")


@app.get("/list", response_model=ListResponse)
async def list_audio_files(
    user_id: str = Query(..., description="User ID to list files for"),
    tag: Optional[str] = Query(None, description="Optional tag to filter by"),
    db: Session = Depends(get_db),
    config: AppConfig = Depends(get_app_config)
) -> ListResponse:
    """
    List audio files for a user with optional tag filtering.
    
    Args:
        user_id: ID of the user to list files for
        tag: Optional tag to filter files by
        db: Database session
        config: Application configuration
        
    Returns:
        ListResponse with user's audio files
    """
    logger = config.logger
    try:
        if not user_id or not user_id.strip():
            raise HTTPException(status_code=400, detail="User ID required")
        
        query = db.query(AudioFile).filter(AudioFile.user_id == user_id.strip())
        
        # Apply tag filter if provided
        if tag and tag.strip():
            # Filter files that contain the specified tag
            tag_lower = tag.strip().lower()
            logger.debug(f"Applying tag filter: {tag_lower}")
            all_files = query.all()
            filtered_files = []
            
            for file_record in all_files:
                file_tags = file_record.get_tags()
                if tag_lower in [t.lower() for t in file_tags]:
                    filtered_files.append(file_record)
            
            files = filtered_files
            logger.info(f"Tag filter applied: found {len(files)} files with tag '{tag}' out of {len(all_files)} total")
        else:
            files = query.all()
            logger.info(f"No tag filter applied: found {len(files)} total files")
        
        # Convert to response format
        file_responses = [AudioFileResponse(**file_record.to_dict()) for file_record in files]
        
        logger.info(f"List request completed for user {user_id}: {len(file_responses)} files returned")
        return ListResponse(
            user_id=user_id.strip(),
            total_count=len(file_responses),
            files=file_responses,
            tag_filter=tag.strip() if tag and tag.strip() else None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list files for user {user_id}: {str(e)}")
        log_database_operation("select", "audio_files", user_id, False, str(e))
        raise HTTPException(status_code=500, detail=f"Failed to list files: {str(e)}")


@app.get("/download")
async def download_user_files(
    user_id: str = Query(..., description="User ID to download files for"),
    db: Session = Depends(get_db),
    config: AppConfig = Depends(get_app_config)
) -> FileResponse:
    """
    Download all audio files for a user as a ZIP archive with metadata.
    
    Args:
        user_id: ID of the user to download files for
        db: Database session
        config: Application configuration
        
    Returns:
        ZIP file containing audio files and metadata
    """
    logger = config.logger
    logger.info(f"Starting download request for user: {user_id}")
    
    try:
        # Validate user ID
        if not user_id or not user_id.strip():
            logger.error("Download request with empty user ID")
            raise HTTPException(status_code=400, detail="User ID is required")
        
        # Query user's files
        logger.debug(f"Querying files for user: {user_id}")
        files = db.query(AudioFile).filter(AudioFile.user_id == user_id.strip()).all()
        log_database_operation("select", "audio_files", user_id, True)
        
        if not files:
            logger.warning(f"No files found for user: {user_id}")
            raise HTTPException(status_code=404, detail="No files found for this user")
        
        logger.info(f"Found {len(files)} files for download for user: {user_id}")
        
        # Prepare file info for ZIP creation
        logger.debug("Preparing file metadata for ZIP creation")
        file_info_list = []
        total_size = 0
        for file_record in files:
            file_dict = file_record.to_dict()
            file_dict['stored_filename'] = file_record.stored_filename  # Add stored filename for ZIP creation
            file_info_list.append(file_dict)
            total_size += file_record.file_size
        
        logger.info(f"Preparing to create ZIP with {len(file_info_list)} files, total size: {total_size} bytes")
        
        # Create ZIP file
        try:
            logger.info("Creating ZIP archive...")
            zip_path = await create_zip_with_metadata(file_info_list, config.upload_dir, config.temp_dir, config.file_config)
            
            # Update metadata with correct timestamp
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as temp_metadata:
                metadata_content = {
                    "export_timestamp": datetime.utcnow().isoformat(),
                    "user_id": user_id.strip(),
                    "total_files": len(file_info_list),
                    "files": file_info_list
                }
                json.dump(metadata_content, temp_metadata, indent=2)
                temp_metadata_path = temp_metadata.name
            
            # Update ZIP with correct metadata
            with zipfile.ZipFile(zip_path, 'a') as zipf:
                zipf.write(temp_metadata_path, "metadata.json")
            
            # Clean up temp metadata file
            os.unlink(temp_metadata_path)
            
            zip_file_size = os.path.getsize(zip_path)
            logger.info(f"ZIP archive created successfully: {zip_path}, size: {zip_file_size} bytes")
            
            download_filename = f"audio_files_{user_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.zip"
            log_file_operation("download", download_filename, user_id, True, zip_file_size)
            
            logger.info(f"Download completed for user {user_id}: {download_filename}")
            
            # Return ZIP file
            return FileResponse(
                path=zip_path,
                filename=download_filename,
                media_type='application/zip',
                background=lambda: cleanup_temp_file(zip_path, config.file_config)  # Clean up after download
            )
            
        except Exception as e:
            logger.error(f"Failed to create ZIP archive for user {user_id}: {str(e)}")
            log_file_operation("download", f"archive_{user_id}", user_id, False, error=str(e))
            raise HTTPException(status_code=500, detail=f"Failed to create download archive: {str(e)}")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Download failed for user {user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")
