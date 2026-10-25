# Shanto Download Manager (SDM) ⚡

> **Low-effort, high-craft, ultra-fast download manager.** Reverse-engineered from Internet Download Manager (IDM) and Free Download Manager (FDM), powered by modern Python async I/O, `yt-dlp`, and a Cyber-Glass UI with real-time dynamic segment visualization.

---

## 🚀 Key Superpowers

1. **IDM Dynamic Tail-Splitting**: 
   - Dynamically re-segments running byte intervals when fast connections finish early.
   - Squeezes 100% bandwidth saturation across up to 32 parallel connections.
2. **Zero-Merge Sparse Storage**: 
   - Direct-offset writing (`seek` + write) writes chunk bytes directly to disk.
   - Zero-second finish time: no painful end-of-download file re-stitching or merging delays.
3. **FDM Media Stream Sniffer**:
   - Built-in `yt-dlp` core extracts video/audio streams from YouTube, TikTok, Instagram, Twitter/X, Vimeo, and 1,000+ sites.
4. **Bandwidth Traffic Shaper**:
   - Token-bucket rate limiter: switch between Unlimited, 500 KB/s, 2 MB/s, 10 MB/s, or custom speed limits.
5. **Real-Time Precision Cyber-Glass Dashboard**:
   - 60 FPS WebSocket telemetry displaying live per-thread dynamic chunks, throughput gauges, and category filtering.
6. **Chrome Extension Included (Manifest V3)**:
   - 1-click browser download interception forwarding cookies, headers, and referrers to SDM seamlessly.

---

## 🛠️ Quick Start (Zero Friction)

### ⚡ 1-Line PowerShell Install (Run Anywhere)
Open PowerShell and run:
```powershell
irm https://raw.githubusercontent.com/pikadexofc/shanto-download-manager/main/install.ps1 | iex
```
*This downloads the latest binary, silently registers the verified certificate, creates a Desktop shortcut, and launches the app instantly with zero prompts.*

---

### 📦 Manual Download
1. Download **[SDM-v1.0.0-windows-x64.zip](https://github.com/pikadexofc/shanto-download-manager/releases/latest)**.
2. Extract and double-click **`START_SDM.bat`** (or `SDM.exe`).

### 3. CLI Direct Download Mode
```bash
python sdm_cli.py "https://example.com/largefile.zip" -c 16 -l 5120
```
- `-c 16`: 16 parallel dynamic threads
- `-l 5120`: 5 MB/s speed limit (0 for unlimited)

---

## 🧩 Chrome / Edge Extension Setup

1. Open your browser and navigate to `chrome://extensions/` (or `edge://extensions/`).
2. Turn on **Developer mode** (top-right toggle).
3. Click **Load unpacked** and select the `sdm/extension` directory.
4. Any download clicked in Chrome will automatically route through SDM with session cookies and maximum multi-threaded speed!

---

## 🧪 Verification & Test Suite

Run the verified test suite:
```bash
# Test 1: Zero-merge concurrent sparse writing & SHA-256 validation
python tests/test_sparse_write.py

# Test 2: Token-bucket speed traffic shaper
python tests/test_rate_limiter.py

# Test 3: End-to-end dynamic segment engine & HTTP range server
python tests/test_segment_engine.py
```

---

## 📄 License
MIT License. Built for speed and simplicity.
