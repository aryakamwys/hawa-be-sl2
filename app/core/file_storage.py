"""
File storage helper untuk upload/download files
"""
import os
import json
import uuid
from pathlib import Path
from typing import Optional, List
from fastapi import UploadFile, HTTPException, status


# Base upload directory
BASE_UPLOAD_DIR = Path(__file__).parent.parent.parent / "uploads"
FEEDBACK_UPLOAD_DIR = BASE_UPLOAD_DIR / "feedbacks"

# Allowed file types
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
MAX_FILES_PER_FEEDBACK = 5


def ensure_upload_directories():
    """Create upload directories if they don't exist"""
    BASE_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    FEEDBACK_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def validate_file(file: UploadFile) -> tuple[str, str]:
    """
    Validate uploaded file
    
    Returns:
        (file_extension, error_message)
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename is required"
        )
    
    file_ext = os.path.splitext(file.filename)[1].lower()
    
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type not allowed. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    
    return file_ext, None


async def save_feedback_files(
    feedback_id: int,
    files: List[UploadFile]
) -> List[str]:
    """
    Save uploaded files for a feedback
    
    Args:
        feedback_id: Feedback ID
        files: List of uploaded files
    
    Returns:
        List of file paths relative to uploads directory
    """
    if len(files) > MAX_FILES_PER_FEEDBACK:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Maximum {MAX_FILES_PER_FEEDBACK} files allowed per feedback"
        )
    
    ensure_upload_directories()
    
    feedback_dir = FEEDBACK_UPLOAD_DIR / str(feedback_id)
    feedback_dir.mkdir(parents=True, exist_ok=True)
    
    saved_paths = []
    
    for idx, file in enumerate(files, start=1):
        # Validate file
        file_ext, _ = validate_file(file)
        
        # Read file content
        content = await file.read()
        
        # Check file size
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File '{file.filename}' exceeds maximum size of {MAX_FILE_SIZE / 1024 / 1024}MB"
            )
        
        # Generate unique filename
        unique_id = str(uuid.uuid4())[:8]
        safe_filename = f"{idx}_{unique_id}{file_ext}"
        file_path = feedback_dir / safe_filename
        
        # Save file
        with open(file_path, "wb") as f:
            f.write(content)
        
        # Store relative path
        relative_path = f"feedbacks/{feedback_id}/{safe_filename}"
        saved_paths.append(relative_path)
    
    return saved_paths


def get_feedback_file_path(relative_path: str) -> Path:
    """
    Get absolute file path from relative path
    
    Args:
        relative_path: Relative path like "feedbacks/1/image_1.jpg"
    
    Returns:
        Absolute Path object
    """
    return BASE_UPLOAD_DIR / relative_path


def delete_feedback_files(feedback_id: int):
    """
    Delete all files for a feedback
    
    Args:
        feedback_id: Feedback ID
    """
    feedback_dir = FEEDBACK_UPLOAD_DIR / str(feedback_id)
    if feedback_dir.exists():
        import shutil
        shutil.rmtree(feedback_dir)


def parse_attachment_paths(attachment_paths_str: Optional[str]) -> List[str]:
    """Parse attachment_paths JSON string to list"""
    if not attachment_paths_str:
        return []
    try:
        return json.loads(attachment_paths_str)
    except (json.JSONDecodeError, TypeError):
        return []


def serialize_attachment_paths(attachment_paths: List[str]) -> str:
    """Serialize attachment_paths list to JSON string"""
    return json.dumps(attachment_paths) if attachment_paths else None

