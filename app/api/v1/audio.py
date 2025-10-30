"""
Audio file management endpoints.
Handles upload, download, listing, and bulk operations with authentication.
"""
import json
import os
import tempfile
import uuid
import zipfile
from datetime import datetime

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
)
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.v1.auth import get_current_user
from app.auth import clean_input
from app.database import AudioFile, User, get_db
from app.logging_config import log_database_operation, log_file_operation
from app.models import (
    AudioFileResponse,
    DownloadRequest,
    ListRequest,
    ListResponse,
    UploadRequest,
    UploadResponse,
)
from app.utils import (
    cleanup_temp_file,
    create_zip_with_metadata,
    generate_unique_filename,
    save_uploaded_file,
    validate_audio_file
)
from app.config import get_app_config

router = APIRouter()


@router.post("/upload", response_model=UploadResponse)
async def upload_audio(
    tags: str = Form(default="", description="Comma-separated tags for the audio file"),
    additional_info: str = Form(default="", description="Additional info about audio file"),
    audio: UploadFile = File(..., description="Audio file to upload"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> UploadResponse:
    """Upload an audio file with metadata"""

    config = get_app_config()
    request_data = UploadRequest(
        user_id=current_user.user_id, 
        tags=clean_input(tags), 
        additional_info=clean_input(additional_info)
    )
    
    is_valid, mime_type = validate_audio_file(audio, config.file_config)
    if not is_valid:
        raise HTTPException(status_code=400, detail=mime_type)
    
    file_id = str(uuid.uuid4())
    unique_filename = generate_unique_filename(audio.filename)
    
    try:
        file_size = await save_uploaded_file(audio, unique_filename, config.upload_dir, config.file_config)
        log_file_operation("upload", audio.filename, request_data.user_id, True, file_size)
    except Exception as e:
        log_file_operation("upload", audio.filename, request_data.user_id, False, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to save file: {e}")
    
    try:
        audio_record = AudioFile(
            id=file_id, user_id=request_data.user_id, original_filename=audio.filename,
            stored_filename=unique_filename, file_size=file_size, mime_type=mime_type,
            upload_timestamp=datetime.utcnow()
        )
        
        audio_record.set_tags(request_data.get_parsed_tags())
        if request_data.has_additional_info():
            audio_record.set_additional_info({"info": request_data.get_parsed_additional_info()})
        
        db.add(audio_record)
        db.commit()
        db.refresh(audio_record)
        log_database_operation("insert", "audio_files", file_id, True)
        
        return UploadResponse(
            status="success", message="File uploaded successfully", file_id=file_id,
            file_info=AudioFileResponse(**audio_record.to_dict())
        )
        
    except Exception as e:
        db.rollback()
        log_database_operation("insert", "audio_files", file_id, False, str(e))
        file_path = config.upload_dir / unique_filename
        if file_path.exists():
            file_path.unlink()
        raise HTTPException(status_code=500, detail=f"Failed to save metadata: {e}")


@router.get("/list", response_model=ListResponse)
async def list_audio_files(
    tag: str = Query(None, description="Tag to filter files by"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> ListResponse:
    """List audio files for a user, optionally filtered by tag"""
    request_data = ListRequest(user_id=current_user.user_id, tag=clean_input(tag) if tag else None)
    all_files = db.query(AudioFile).filter(AudioFile.user_id == request_data.user_id).all()
    files = request_data.apply_tag_filter(all_files)
    
    return ListResponse(
        user_id=request_data.user_id,
        total_count=len(files),
        files=[AudioFileResponse(**file_record.to_dict()) for file_record in files],
        tag_filter=request_data.tag if request_data.has_tag_filter() else None
    )


@router.get("/download")
async def download_user_files(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> FileResponse:
    """Download all audio files for a user as a ZIP archive with metadata"""

    config = get_app_config()
    request_data = DownloadRequest(user_id=current_user.user_id)
    
    files = db.query(AudioFile).filter(AudioFile.user_id == request_data.user_id).all()
    log_database_operation("select", "audio_files", request_data.user_id, True)
    
    if not files:
        raise HTTPException(status_code=404, detail="No files found for this user")
    
    file_info_list = request_data.prepare_file_info_list(files)
    
    try:
        zip_path = await create_zip_with_metadata(file_info_list, config.upload_dir, config.temp_dir, config.file_config)
        
        metadata_content = request_data.create_metadata_content(file_info_list)
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as temp_metadata:
            json.dump(metadata_content, temp_metadata, indent=2)
            temp_metadata_path = temp_metadata.name
        
        with zipfile.ZipFile(zip_path, 'a') as zipf:
            zipf.write(temp_metadata_path, "metadata.json")
        os.unlink(temp_metadata_path)
        
        download_filename = request_data.generate_download_filename()
        log_file_operation("download", download_filename, request_data.user_id, True, os.path.getsize(zip_path))
        
        # Schedule cleanup of temporary file after response is sent
        background_tasks.add_task(cleanup_temp_file, zip_path, config.file_config)
        
        return FileResponse(
            path=zip_path, filename=download_filename, media_type='application/zip'
        )
    except Exception as e:
        log_file_operation("download", f"archive_{request_data.user_id}", request_data.user_id, False, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to create download archive: {e}")
