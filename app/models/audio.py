"""
Pydantic models for audio file operations.
Defines request/response schemas for upload, download, and listing endpoints.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, validator

from app.models.common import AudioFileResponse, validate_user_id_field


class UploadRequest(BaseModel):
    user_id: str
    tags: str = ""
    additional_info: str = ""

    @validator('user_id')
    def validate_user_id(cls, v):
        return validate_user_id_field(cls, v)

    @validator('tags', 'additional_info')
    def validate_strings(cls, v):
        if v is None:
            return ""
        return v.strip()

    def get_parsed_tags(self) -> List[str]:
        """Parse comma-separated tags into a list"""
        if not self.tags:
            return []
        return [tag.strip() for tag in self.tags.split(",") if tag.strip()]

    def get_parsed_additional_info(self) -> str:
        """Get cleaned additional info"""
        return self.additional_info.strip()

    def has_additional_info(self) -> bool:
        """Check if additional info is provided"""
        return bool(self.additional_info.strip())

    class Config:
        from_attributes = True


class UploadResponse(BaseModel):
    status: str
    message: str
    file_id: Optional[str] = None
    file_info: Optional[AudioFileResponse] = None

    class Config:
        from_attributes = True


class ListRequest(BaseModel):
    user_id: str
    tag: Optional[str] = None

    @validator('user_id')
    def validate_user_id(cls, v):
        return validate_user_id_field(cls, v)

    @validator('tag')
    def validate_tag(cls, v):
        return v.strip() if v and v.strip() else None

    def has_tag_filter(self) -> bool:
        return bool(self.tag)

    def get_tag_filter(self) -> Optional[str]:
        return self.tag.lower() if self.tag else None

    def apply_tag_filter(self, files_with_tags) -> List:
        if not self.has_tag_filter():
            return files_with_tags
        
        tag_filter = self.get_tag_filter()
        return [f for f in files_with_tags if tag_filter in [t.lower() for t in f.get_tags()]]

    class Config:
        from_attributes = True


class ListResponse(BaseModel):
    user_id: str
    total_count: int
    files: List[AudioFileResponse]
    tag_filter: Optional[str] = None

    class Config:
        from_attributes = True


class DownloadRequest(BaseModel):
    user_id: str

    @validator('user_id')
    def validate_user_id(cls, v):
        return validate_user_id_field(cls, v)

    def prepare_file_info_list(self, files) -> List[Dict]:
        return [{**f.to_dict(), 'stored_filename': f.stored_filename} for f in files]

    def generate_download_filename(self) -> str:
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        return f"audio_files_{self.user_id}_{timestamp}.zip"

    def create_metadata_content(self, file_info_list: List[Dict]) -> Dict:
        return {
            "export_timestamp": datetime.utcnow().isoformat(),
            "user_id": self.user_id,
            "total_files": len(file_info_list),
            "files": file_info_list
        }

    class Config:
        from_attributes = True
