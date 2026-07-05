import re
import uuid
from pathlib import Path


class LocalDiskStorage:
    """Starter FileStorage: local disk, one directory per org. Swap for an
    EU-region S3-compatible adapter later (NFR-01) — same interface."""

    def __init__(self, base_dir: Path):
        self.base_dir = Path(base_dir)

    def save(self, org_id: str, filename: str, content: bytes) -> str:
        safe = re.sub(r"[^A-Za-z0-9._-]", "_", filename)[-100:] or "bestand"
        key = f"{org_id}/{uuid.uuid4().hex}-{safe}"
        path = self.base_dir / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return key

    def load(self, storage_key: str) -> bytes:
        path = (self.base_dir / storage_key).resolve()
        if not path.is_relative_to(self.base_dir.resolve()):
            raise ValueError("storage key escapes base directory")
        return path.read_bytes()
