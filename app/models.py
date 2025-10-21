"""
Request/response models
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, validator

class AudioFileResponse(BaseModel):
    id: str
    user_id: str
    original_filename: str
    file_size: int
    mime_type: str
    tags: List[str] = []
    additional_metadata: Optional[Dict[str, Any]] = None
    upload_timestamp: str

    class Config:
        from_attributes = True
        json_encoders = {datetime: lambda v: v.isoformat()}


class UploadResponse(BaseModel):
    status: str
    message: str
    file_id: Optional[str] = None
    file_info: Optional[AudioFileResponse] = None

    class Config:
        from_attributes = True


class ListResponse(BaseModel):
    user_id: str
    total_count: int
    files: List[AudioFileResponse]
    tag_filter: Optional[str] = None

    class Config:
        from_attributes = True


class UploadRequest(BaseModel):
    user_id: str
    tags: List[str] = []
    additional_metadata: Optional[Dict[str, Any]] = None

    @validator('user_id')
    def validate_user_id(cls, v):
        if not v or not v.strip():
            raise ValueError('User ID required')
        return v.strip()

    @validator('tags')
    def validate_tags(cls, v):
        if v is None:
            return []
        # Remove empty/duplicate tags
        cleaned = []
        seen = set()
        for tag in v:
            if isinstance(tag, str) and tag.strip() and tag.strip() not in seen:
                clean_tag = tag.strip().lower()
                cleaned.append(clean_tag)
                seen.add(clean_tag)
        return cleaned

    class Config:
        from_attributes = True
