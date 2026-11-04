from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional, Set

_LOGGER = logging.getLogger(__name__)

# Use persistent storage alongside local image thumbnails
THUMBNAILS_DIR = Path(os.environ.get("THUMBNAILS_DIR", "/thumbnails"))
CACHE_DIR = THUMBNAILS_DIR / "tv"


class TVThumbnailCache:
    def __init__(self):
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def _cache_path(self, content_id: str) -> Path:
        # Sanitize content_id for safe filename
        safe_id = content_id.replace("/", "_").replace("\\", "_")
        return CACHE_DIR / f"{safe_id}.jpg"

    def get(self, content_id: str) -> Optional[bytes]:
        path = self._cache_path(content_id)
        if path.exists():
            _LOGGER.debug(f"Cache hit for thumbnail: {content_id}")
            try:
                return path.read_bytes()
            except OSError as e:
                _LOGGER.warning(f"Failed to read cached thumbnail {path}: {e}")
                return None
        return None

    def set(self, content_id: str, data: bytes) -> None:
        path = self._cache_path(content_id)
        temp_path = path.with_suffix(".tmp")
        try:
            temp_path.write_bytes(data)
            temp_path.replace(path)
            _LOGGER.debug(f"Cached thumbnail: {content_id}")
        except OSError as e:
            _LOGGER.warning(f"Failed to write cached thumbnail {path}: {e}")

    def invalidate(self, content_id: str) -> None:
        path = self._cache_path(content_id)
        try:
            path.unlink(missing_ok=True)
            _LOGGER.debug(f"Invalidated cache for: {content_id}")
        except OSError as e:
            _LOGGER.warning(f"Failed to invalidate thumbnail {path}: {e}")

    def clear(self) -> None:
        """Clear all cached thumbnails."""
        for path in CACHE_DIR.glob("*.jpg"):
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
        _LOGGER.info("Cleared all thumbnail cache")

    def cleanup_orphaned(self, valid_content_ids: set[str]) -> int:
        """Remove cached thumbnails that are no longer on the TV.
        
        Args:
            valid_content_ids: Set of content_ids currently on the TV
            
        Returns:
            Number of orphaned thumbnails removed
        """
        removed = 0
        for path in CACHE_DIR.glob("*.jpg"):
            # Extract content_id from filename (reverse of _cache_path sanitization)
            cached_id = path.stem.replace("_", "/")
            # Also try without replacement in case content_id had no slashes
            if cached_id not in valid_content_ids and path.stem not in valid_content_ids:
                try:
                    path.unlink(missing_ok=True)
                    removed += 1
                    _LOGGER.debug(f"Removed orphaned thumbnail: {path.stem}")
                except OSError:
                    pass
        
        if removed:
            _LOGGER.info(f"Cleaned up {removed} orphaned TV thumbnail(s)")
        return removed
