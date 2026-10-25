"""Sparse File Pre-allocation and Zero-Merge Direct-Offset Storage Engine.
Reverse-Engineered from IDM's High-Throughput Disk I/O Architecture.
"""

from __future__ import annotations

import ctypes
import hashlib
import os
import platform
import threading
from pathlib import Path
from typing import Optional


class SparseFileWriter:
    """Thread-safe direct-offset sparse file writer.

    Allows N worker threads to write chunk data directly into target byte offsets
    simultaneously without creating temporary chunk files or requiring an end-of-download
    merge/stitch operation.
    """

    def __init__(self, file_path: str, total_size: int = 0):
        self.file_path = Path(file_path).resolve()
        self.total_size = total_size
        self._lock = threading.Lock()
        self._fp = None
        self._is_open = False

    def open(self) -> None:
        """Create directory, pre-allocate space if size > 0, and open handle."""
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        # Open in read/write binary mode; create if not exists
        if not self.file_path.exists():
            with open(self.file_path, "wb") as f:
                if self.total_size > 0:
                    self._preallocate_sparse(f, self.total_size)

        self._fp = open(self.file_path, "r+b")
        self._is_open = True

    def _preallocate_sparse(self, f, size: int) -> None:
        """Pre-allocate file space efficiently on Windows or Unix without zero-filling delay."""
        try:
            if platform.system() == "Windows":
                # Seek to size - 1 and write 1 byte to reserve file length
                f.seek(size - 1)
                f.write(b"\0")
                f.flush()
            else:
                # On POSIX, use posix_fallocate or truncate
                try:
                    os.posix_fallocate(f.fileno(), 0, size)
                except (AttributeError, OSError):
                    f.truncate(size)
        except Exception:
            # Fallback
            f.truncate(size)

    def write_at(self, offset: int, data: bytes) -> int:
        """Write bytes directly at a specific absolute byte offset."""
        if not self._is_open or not self._fp:
            raise RuntimeError("SparseFileWriter is not open")

        with self._lock:
            self._fp.seek(offset)
            self._fp.write(data)
            return len(data)

    def flush(self) -> None:
        if self._is_open and self._fp:
            with self._lock:
                self._fp.flush()

    def close(self) -> None:
        with self._lock:
            if self._is_open and self._fp:
                try:
                    self._fp.flush()
                    self._fp.close()
                except Exception:
                    pass
                finally:
                    self._fp = None
                    self._is_open = False

    def __enter__(self) -> SparseFileWriter:
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    @staticmethod
    def compute_sha256(file_path: str, chunk_size: int = 1024 * 1024) -> str:
        """Compute SHA-256 hash of completed file for bit-perfect integrity validation."""
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(chunk_size):
                h.update(chunk)
        return h.hexdigest()

    @staticmethod
    def compute_md5(file_path: str, chunk_size: int = 1024 * 1024) -> str:
        """Compute MD5 hash."""
        h = hashlib.md5()
        with open(file_path, "rb") as f:
            while chunk := f.read(chunk_size):
                h.update(chunk)
        return h.hexdigest()
