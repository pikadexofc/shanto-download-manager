"""Shanto Download Manager (SDM) Data Models & SQLite Persistence.
Reverse-Engineered State Management for Resilient Resumption.
"""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    CONNECTING = "CONNECTING"
    DOWNLOADING = "DOWNLOADING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    ERROR = "ERROR"
    CANCELLED = "CANCELLED"


class TaskCategory(str, Enum):
    COMPRESSED = "Compressed"
    VIDEO = "Video"
    AUDIO = "Audio"
    DOCUMENTS = "Documents"
    PROGRAMS = "Programs"
    OTHER = "Other"


@dataclass
class SegmentState:
    segment_id: int
    start_byte: int
    current_byte: int
    end_byte: int
    status: str = "PENDING"  # PENDING, ACTIVE, FINISHED, ERROR
    speed_bps: float = 0.0

    @property
    def total_bytes(self) -> int:
        return max(0, self.end_byte - self.start_byte + 1)

    @property
    def downloaded_bytes(self) -> int:
        return max(0, self.current_byte - self.start_byte)

    @property
    def remaining_bytes(self) -> int:
        return max(0, self.end_byte - self.current_byte + 1)

    @property
    def progress(self) -> float:
        tot = self.total_bytes
        if tot <= 0:
            return 1.0 if self.status == "FINISHED" else 0.0
        return min(1.0, max(0.0, self.downloaded_bytes / tot))


@dataclass
class DownloadTask:
    task_id: str
    url: str
    filename: str
    save_path: str
    category: TaskCategory = TaskCategory.OTHER
    total_size: int = 0
    downloaded_bytes: int = 0
    status: TaskStatus = TaskStatus.PENDING
    speed_bps: float = 0.0
    eta_seconds: float = 0.0
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    resumable: bool = True
    error_message: Optional[str] = None
    headers: Dict[str, str] = field(default_factory=dict)
    segments: List[SegmentState] = field(default_factory=list)
    speed_limit_kbps: int = 0  # 0 = unlimited
    sequential: bool = False  # Sequential downloading for instant stream preview

    @property
    def progress(self) -> float:
        if self.total_size <= 0:
            return 1.0 if self.status == TaskStatus.COMPLETED else 0.0
        return min(1.0, max(0.0, self.downloaded_bytes / self.total_size))

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        d["category"] = self.category.value
        d["progress"] = round(self.progress * 100, 2)
        d["sequential"] = self.sequential
        d["speed_formatted"] = self.format_speed(self.speed_bps)
        d["size_formatted"] = self.format_size(self.total_size)
        d["downloaded_formatted"] = self.format_size(self.downloaded_bytes)
        d["segments"] = [
            {
                "id": s.segment_id,
                "start": s.start_byte,
                "current": s.current_byte,
                "end": s.end_byte,
                "progress": round(s.progress * 100, 1),
                "status": s.status,
                "speed": self.format_speed(s.speed_bps),
            }
            for s in self.segments
        ]
        return d

    @staticmethod
    def format_size(bytes_val: int) -> str:
        if bytes_val <= 0:
            return "0 B"
        units = ["B", "KB", "MB", "GB", "TB"]
        idx = 0
        val = float(bytes_val)
        while val >= 1024.0 and idx < len(units) - 1:
            val /= 1024.0
            idx += 1
        return f"{val:.2f} {units[idx]}"

    @staticmethod
    def format_speed(bps: float) -> str:
        if bps <= 0:
            return "0 B/s"
        units = ["B/s", "KB/s", "MB/s", "GB/s"]
        idx = 0
        val = float(bps)
        while val >= 1024.0 and idx < len(units) - 1:
            val /= 1024.0
            idx += 1
        return f"{val:.2f} {units[idx]}"


def detect_category(filename: str) -> TaskCategory:
    ext = Path(filename).suffix.lower()
    if ext in [".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".iso"]:
        return TaskCategory.COMPRESSED
    if ext in [".mp4", ".mkv", ".webm", ".avi", ".mov", ".flv", ".ts", ".m4v"]:
        return TaskCategory.VIDEO
    if ext in [".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a", ".opus"]:
        return TaskCategory.AUDIO
    if ext in [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".epub"]:
        return TaskCategory.DOCUMENTS
    if ext in [".exe", ".msi", ".dmg", ".pkg", ".deb", ".rpm", ".apk", ".appimage"]:
        return TaskCategory.PROGRAMS
    return TaskCategory.OTHER


class StateDB:
    """Thread-safe SQLite store for downloads and segment checkpoints."""

    def __init__(self, db_path: str = "sdm.db"):
        self.db_path = db_path
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=15.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    url TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    save_path TEXT NOT NULL,
                    category TEXT NOT NULL,
                    total_size INTEGER DEFAULT 0,
                    downloaded_bytes INTEGER DEFAULT 0,
                    status TEXT NOT NULL,
                    resumable INTEGER DEFAULT 1,
                    error_message TEXT,
                    headers_json TEXT,
                    segments_json TEXT,
                    speed_limit_kbps INTEGER DEFAULT 0,
                    created_at REAL,
                    updated_at REAL
                )
                """
            )
            conn.commit()

    def save_task(self, task: DownloadTask) -> None:
        with self._get_conn() as conn:
            headers_json = json.dumps(task.headers)
            segments_json = json.dumps([asdict(s) for s in task.segments])
            conn.execute(
                """
                INSERT OR REPLACE INTO tasks (
                    task_id, url, filename, save_path, category,
                    total_size, downloaded_bytes, status, resumable,
                    error_message, headers_json, segments_json,
                    speed_limit_kbps, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task.task_id,
                    task.url,
                    task.filename,
                    task.save_path,
                    task.category.value,
                    task.total_size,
                    task.downloaded_bytes,
                    task.status.value,
                    1 if task.resumable else 0,
                    task.error_message,
                    headers_json,
                    segments_json,
                    task.speed_limit_kbps,
                    task.created_at,
                    time.time(),
                ),
            )
            conn.commit()

    def get_task(self, task_id: str) -> Optional[DownloadTask]:
        with self._get_conn() as conn:
            cur = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,))
            row = cur.fetchone()
            if not row:
                return None
            return self._row_to_task(row)

    def list_tasks(self) -> List[DownloadTask]:
        with self._get_conn() as conn:
            cur = conn.execute("SELECT * FROM tasks ORDER BY created_at DESC")
            return [self._row_to_task(r) for r in cur.fetchall()]

    def delete_task(self, task_id: str) -> bool:
        with self._get_conn() as conn:
            cur = conn.execute("DELETE FROM tasks WHERE task_id = ?", (task_id,))
            conn.commit()
            return cur.rowcount > 0

    def _row_to_task(self, row: sqlite3.Row) -> DownloadTask:
        headers = json.loads(row["headers_json"] or "{}")
        segments_raw = json.loads(row["segments_json"] or "[]")
        segments = [SegmentState(**s) for s in segments_raw]

        task = DownloadTask(
            task_id=row["task_id"],
            url=row["url"],
            filename=row["filename"],
            save_path=row["save_path"],
            category=TaskCategory(row["category"]),
            total_size=row["total_size"],
            downloaded_bytes=row["downloaded_bytes"],
            status=TaskStatus(row["status"]),
            resumable=bool(row["resumable"]),
            error_message=row["error_message"],
            headers=headers,
            segments=segments,
            speed_limit_kbps=row["speed_limit_kbps"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
        return task
