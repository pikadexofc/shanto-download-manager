"""Media Stream Extractor and HLS/Video Sniffer.
Reverse-Engineered from Free Download Manager (FDM)'s Media Pipeline and yt-dlp Core.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional
import yt_dlp


class StreamExtractor:
    """Extracts media stream formats and direct links from video platforms."""

    @staticmethod
    def is_media_url(url: str) -> bool:
        lower = url.lower()
        domains = [
            "youtube.com", "youtu.be", "vimeo.com", "tiktok.com",
            "facebook.com", "fb.watch", "instagram.com", "twitter.com",
            "x.com", "twitch.tv", "dailymotion.com", "bilibili.com"
        ]
        return any(d in lower for d in domains) or ".m3u8" in lower or ".mpd" in lower

    @classmethod
    async def extract_info(cls, url: str) -> Dict[str, Any]:
        """Extract media title, thumbnail, duration, and available format streams."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, cls._sync_extract, url)

    @staticmethod
    def _sync_extract(url: str) -> Dict[str, Any]:
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "extract_flat": False,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(url, download=False)
                if not info:
                    raise ValueError("Could not extract info")

                formats: List[Dict[str, Any]] = []
                raw_formats = info.get("formats", [])
                for f in raw_formats:
                    # Filter for useful video/audio streams
                    vcodec = f.get("vcodec", "none")
                    acodec = f.get("acodec", "none")
                    height = f.get("height")
                    ext = f.get("ext", "mp4")
                    f_id = f.get("format_id")
                    f_url = f.get("url")

                    label = f"{height}p" if height else (f.get("format_note") or ext)
                    if vcodec != "none" and acodec != "none":
                        label += " (Video+Audio)"
                    elif vcodec != "none":
                        label += " (Video Only)"
                    elif acodec != "none":
                        label = f"Audio ({acodec})"

                    filesize = f.get("filesize") or f.get("filesize_approx") or 0

                    formats.append({
                        "format_id": f_id,
                        "label": label,
                        "resolution": f"{f.get('width', 0)}x{height}" if height else "Audio",
                        "ext": ext,
                        "filesize": filesize,
                        "vcodec": vcodec,
                        "acodec": acodec,
                        "url": f_url,
                        "is_direct": bool(f_url and f_url.startswith("http")),
                    })

                # Sort formats from highest to lowest resolution
                formats.sort(key=lambda x: (x.get("filesize") or 0), reverse=True)

                return {
                    "title": info.get("title", "Unknown Media"),
                    "thumbnail": info.get("thumbnail"),
                    "duration": info.get("duration", 0),
                    "uploader": info.get("uploader", ""),
                    "formats": formats[:15],  # top 15 clean formats
                }
            except Exception as e:
                raise RuntimeError(f"Stream extraction failed: {e}")

    @classmethod
    async def download_media(
        cls,
        url: str,
        output_path: str,
        format_id: Optional[str] = None,
        progress_hook: Optional[Any] = None,
    ) -> str:
        """Download high quality media directly via optimized yt-dlp runner."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, cls._sync_download, url, output_path, format_id, progress_hook
        )

    @staticmethod
    def _sync_download(
        url: str,
        output_path: str,
        format_id: Optional[str],
        progress_hook: Optional[Any],
    ) -> str:
        target = Path(output_path).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)

        ydl_opts = {
            "outtmpl": str(target),
            "quiet": True,
            "no_warnings": True,
            "concurrent_fragment_downloads": 8,  # fast multi-fragment pulling
        }

        if format_id:
            ydl_opts["format"] = format_id
        else:
            ydl_opts["format"] = "bestvideo+bestaudio/best"

        if progress_hook:
            ydl_opts["progress_hooks"] = [progress_hook]

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        return str(target)
