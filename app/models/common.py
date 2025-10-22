from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, validator

def validate_user_id_field(cls, v):
    """Shared validator for user_id fields"""
    if not v or not v.strip():
        raise ValueError('User ID required')
    return v.strip()

class AudioFileResponse(BaseModel):
    id: str
    user_id: str
    original_filename: str
    file_size: int
    mime_type: str
    tags: List[str] = []
    additional_info: Optional[Dict[str, Any]] = None
    upload_timestamp: str

    class Config:
        from_attributes = True
        json_encoders = {datetime: lambda v: v.isoformat()}