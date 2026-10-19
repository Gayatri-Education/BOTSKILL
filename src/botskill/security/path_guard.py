"""BOTSKILL — Filesystem Path Traversal & Sandbox Confinement Guard."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from botskill.learning.sanitizer import SecurityError


class PathTraversalGuard:
    """Enforces strict filesystem jail boundaries to prevent arbitrary file read/write."""

    def __init__(self, allowed_base_dir: Optional[Path] = None):
        if allowed_base_dir is None:
            # Base of current botskill workspace
            allowed_base_dir = Path(__file__).resolve().parent.parent.parent.parent
        self.base_dir = allowed_base_dir.resolve()

    def validate_safe_path(self, user_supplied_path: str) -> Path:
        """Resolves path and enforces that it remains strictly inside the allowed workspace boundary."""
        if not user_supplied_path:
            raise SecurityError("Path traversal violation: Empty path provided.")

        # Null-byte injection check
        if "\0" in user_supplied_path:
            raise SecurityError("Path traversal violation: Null byte detected in file path.")

        # Check raw string for suspicious parent-directory escapes before resolution
        cleaned = user_supplied_path.replace("\\", "/")
        if "/../" in cleaned or cleaned.startswith("../") or cleaned.endswith("/.."):
            pass  # Will be tested against resolve boundary

        try:
            target = Path(user_supplied_path)
            if not target.is_absolute():
                resolved = (self.base_dir / target).resolve()
            else:
                resolved = target.resolve()
        except Exception as e:
            raise SecurityError(f"Path traversal violation: Invalid path resolution ({e})")

        # Boundary confinement test: resolved must start with self.base_dir
        try:
            resolved.relative_to(self.base_dir)
        except ValueError:
            raise SecurityError(
                f"Path traversal violation: Target '{user_supplied_path}' escapes sandbox boundary '{self.base_dir}'."
            )

        return resolved
