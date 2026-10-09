import os
import re
from pathlib import Path
from uuid import uuid4

ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ("jpg", b"\xff\xd8\xff"),
    "image/png": ("png", b"\x89PNG\r\n\x1a\n"),
    "image/gif": ("gif", b"GIF8"),
    "image/webp": ("webp", b"RIFF"),
}
IMAGE_MAX_BYTES = 5 * 1024 * 1024
FILE_REFERENCE_PATTERN = re.compile(r"^file:proofs/[0-9a-f]{32}\.(jpg|png|gif|webp)$")


def storage_directory() -> Path:
    configured = os.getenv("FILE_STORAGE_PATH")
    if configured:
        return Path(configured).expanduser().resolve() / "proofs"
    return Path(__file__).resolve().parents[1] / "data" / "proofs"


def store_image(content_type: str | None, content: bytes) -> str:
    image_format = ALLOWED_IMAGE_TYPES.get(content_type or "")
    if image_format is None:
        raise ValueError("Proof image must be JPEG, PNG, GIF, or WebP")
    extension, signature = image_format
    if len(content) > IMAGE_MAX_BYTES:
        raise ValueError("Proof image exceeds the 5 MB upload limit")
    if len(content) < len(signature) or not content.startswith(signature):
        raise ValueError("Image content does not match its declared image type")
    if content_type == "image/webp" and content[8:12] != b"WEBP":
        raise ValueError("Image content does not match its declared image type")

    directory = storage_directory()
    directory.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid4().hex}.{extension}"
    temporary_path = directory / f"{filename}.tmp"
    final_path = directory / filename
    try:
        temporary_path.write_bytes(content)
        temporary_path.replace(final_path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()
    return f"file:proofs/{filename}"


def resolve_image(reference: str) -> tuple[Path, str] | None:
    match = FILE_REFERENCE_PATTERN.fullmatch(reference)
    if match is None:
        return None
    directory = storage_directory()
    path = (directory / reference.removeprefix("file:proofs/")).resolve()
    if path.parent != directory:
        return None
    if not path.is_file():
        raise FileNotFoundError("Stored proof image is missing")
    content_type = {
        "jpg": "image/jpeg",
        "png": "image/png",
        "gif": "image/gif",
        "webp": "image/webp",
    }[match.group(1)]
    return path, content_type


def delete_image(reference: str | None) -> None:
    if reference is None:
        return
    resolved = resolve_image(reference)
    if resolved is None:
        return
    path, _ = resolved
    try:
        path.unlink()
    except FileNotFoundError:
        pass
