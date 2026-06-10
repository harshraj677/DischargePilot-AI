import os
import uuid
import hashlib
from pathlib import Path
from typing import Tuple

from app.config import settings
from app.utils.exceptions import InvalidFileTypeException, FileTooLargeException, StorageException
from app.utils.logging import get_logger

logger = get_logger(__name__)


def validate_file_upload(filename: str, file_size: int) -> None:
    ext = Path(filename).suffix.lower()
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise InvalidFileTypeException(filename, settings.ALLOWED_EXTENSIONS)
    if file_size > settings.max_file_size_bytes:
        raise FileTooLargeException(filename, settings.MAX_FILE_SIZE_MB)


def build_patient_upload_dir(patient_id: str) -> Path:
    patient_dir = Path(settings.UPLOAD_DIR) / patient_id
    patient_dir.mkdir(parents=True, exist_ok=True)
    return patient_dir


def generate_stored_filename(original_filename: str) -> str:
    stem = Path(original_filename).stem
    safe_stem = "".join(c if c.isalnum() or c in "-_" else "_" for c in stem)[:60]
    unique_id = uuid.uuid4().hex[:8]
    ext = Path(original_filename).suffix.lower()
    return f"{safe_stem}_{unique_id}{ext}"


async def save_upload_file(file_bytes: bytes, patient_id: str, original_filename: str) -> Tuple[str, int]:
    try:
        patient_dir = build_patient_upload_dir(patient_id)
        stored_name = generate_stored_filename(original_filename)
        file_path = patient_dir / stored_name

        with open(file_path, "wb") as f:
            f.write(file_bytes)

        actual_size = file_path.stat().st_size
        logger.info("File saved", path=str(file_path), size_bytes=actual_size)
        return str(file_path), actual_size

    except OSError as e:
        raise StorageException(f"Failed to save file '{original_filename}': {e}")


def delete_file(file_path: str) -> bool:
    try:
        path = Path(file_path)
        if path.exists():
            path.unlink()
            logger.info("File deleted", path=file_path)
            return True
        return False
    except OSError as e:
        logger.error("Failed to delete file", path=file_path, error=str(e))
        return False


def compute_file_hash(file_path: str) -> str:
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def get_file_size(file_path: str) -> int:
    return os.path.getsize(file_path)
