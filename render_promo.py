"""Ultra-High-Craft Motion Video Generator for Shanto Download Manager (SDM).
Synchronized to ElevenLabs Voiceover Audio track.
"""

from __future__ import annotations

import math
import subprocess
import sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

WIDTH, HEIGHT = 1920, 1080
FPS = 30
TOTAL_DURATION = 56.7
TOTAL_FRAMES = int(TOTAL_DURATION * FPS)
AUDIO_PATH = r"C:\Users\Shanto\.gemini\antigravity\brain\0067f637-d98f-47e5-8013-5f47b573dc96\.user_uploaded\uploaded_media_1792963010469.mp3"
OUTPUT_MP4 = r"f:\st leads\sdm\SDM_Official_Launch_Reel.mp4"

# Load Fonts
FONT_TITLE = ImageFont.truetype(r"C:\Windows\Fonts\segoeuib.ttf", 64)
FONT_SUBTITLE = ImageFont.truetype(r"C:\Windows\Fonts\segoeuib.ttf", 36)
FONT_BODY = ImageFont.truetype(r"C:\Windows\Fonts\segoeui.ttf", 26)
FONT_MONO = ImageFont.truetype(r"C:\Windows\Fonts\consola.ttf", 24)
FONT_MONO_SM = ImageFont.truetype(r"C:\Windows\Fonts\consola.ttf", 18)
FONT_HERO = ImageFont.truetype(r"C:\Windows\Fonts\segoeuib.ttf", 80)


def draw_rounded_rect(draw, bbox, radius, fill, outline=None, width=1):
    x0, y0, x1, y1 = bbox
    draw.rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=fill, outline=outline, width=width)


# Pre-compute 60 ambient background frames for 10x rendering speed
BG_CACHE = []

def init_bg_cache():
    print("[Renderer] Pre-computing smooth 60-frame chromatic aurora background...")
    for f in range(60):
        t = f / FPS
        img = Image.new("RGBA", (WIDTH, HEIGHT), (10, 12, 16, 255))
        cx = int(WIDTH * 0.5 + math.sin(t * 1.5) * 160)
        cy = int(HEIGHT * 0.45 + math.cos(t * 1.2) * 110)
        
        glow = Image.new("RGBA", (300, 300), (0, 0, 0, 0))
        gdraw = ImageDraw.Draw(glow)
        gdraw.ellipse([30, 30, 270, 270], fill=(0, 229, 255, 38))
        gdraw.ellipse([70, 70, 230, 230], fill=(179, 136, 255, 32))
        glow = glow.filter(ImageFilter.GaussianBlur(radius=40))
        glow_lg = glow.resize((1000, 1000), Image.Resampling.BILINEAR)
        img.paste(glow_lg, (cx - 500, cy - 500), glow_lg)
        BG_CACHE.append(img)
    print("[Renderer] Ambient aurora cache ready.")

def create_ambient_bg(frame_idx: int) -> Image.Image:
    return BG_CACHE[frame_idx % len(BG_CACHE)].copy()


def render_frame(frame_idx: int) -> Image.Image:
    t = frame_idx / FPS
    base = create_ambient_bg(frame_idx)
    draw = ImageDraw.Draw(base)

    # Top Minimal Precision Bar
    draw_rounded_rect(draw, [40, 30, 420, 75], radius=8, fill=(20, 24, 33, 200), outline=(255, 255, 255, 20))
    draw.text((60, 42), "PIXELPIE MEDIA • SDM TURBO", font=FONT_MONO_SM, fill=(0, 229, 255, 240))
    draw.text((WIDTH - 280, 42), f"TIME {t:05.2f}s // 60 FPS", font=FONT_MONO_SM, fill=(140, 150, 165, 200))

    # =========================================================================
    # SCENE 1: 0.0s - 11.5s | THE PROBLEM ("Download managers shouldn't be messy")
    # =========================================================================
    if t < 11.5:
        # Title text
        draw.text((WIDTH // 2 - 440, 150), "Download managers shouldn't be messy.", font=FONT_TITLE, fill=(245, 248, 252, 255))
        
        # Retro ugly window
        win_w, win_h = 900, 480
        wx = (WIDTH - win_w) // 2
        wy = 280
        
        if t < 10.8:
            # Draw 90s vintage grey window
            draw.rectangle([wx, wy, wx + win_w, wy + win_h], fill=(192, 192, 192, 255), outline=(64, 64, 64, 255), width=3)
            # Window Header
            draw.rectangle([wx + 3, wy + 3, wx + win_w - 3, wy + 38], fill=(0, 0, 128, 255))
            draw.text((wx + 15, wy + 8), "Legacy Download Accelerator v2.4 (Not Responding)", font=FONT_BODY, fill=(255, 255, 255, 255))
            
            # Ugly cluttered buttons row
            btn_labels = ["Pause", "Resume", "Redial", "Stop", "Batch", "FTP Tree", "Properties", "Buy Pro!"]
            for i, bl in enumerate(btn_labels):
                bx = wx + 20 + i * 108
                draw.rectangle([bx, wy + 55, bx + 100, wy + 90], fill=(215, 215, 215, 255), outline=(100, 100, 100, 255))
                draw.text((bx + 12, wy + 62), bl, font=FONT_MONO_SM, fill=(0, 0, 0, 255))
            
            # Stalled Progress Bar
            draw.rectangle([wx + 40, wy + 160, wx + win_w - 40, wy + 210], fill=(255, 255, 255, 255), outline=(80, 80, 80, 255))
            # 14% progress
            prog_w = int((win_w - 80) * 0.14)
            draw.rectangle([wx + 40, wy + 160, wx + 40 + prog_w, wy + 210], fill=(0, 0, 180, 255))
            draw.text((wx + win_w // 2 - 120, wy + 172), "14% Stalled (Time remaining: 42 mins)", font=FONT_BODY, fill=(255, 0, 0, 255) if int(t * 4) % 2 == 0 else (0, 0, 0, 255))
            
            # Annoying Pop-up box
            draw_rounded_rect(draw, [wx + 200, wy + 250, wx + win_w - 200, wy + 420], radius=4, fill=(255, 255, 220, 255), outline=(200, 0, 0, 255), width=2)
            draw.text((wx + 220, wy + 270), "⚠ WARNING: UNPLAYABLE FILE", font=FONT_BODY, fill=(180, 0, 0, 255))
            draw.text((wx + 220, wy + 310), "File pieces scattered across disk.\nYou cannot watch or open this movie until 100% finishes.", font=FONT_MONO_SM, fill=(40, 40, 40, 255))
        else:
            # Shatter transition on [thud]
            shatter_prog = (t - 10.8) / 0.7
            np.random.seed(int(frame_idx))
            for _ in range(80):
                px = wx + np.random.randint(0, win_w) + int(np.random.randn() * shatter_prog * 250)
                py = wy + np.random.randint(0, win_h) + int(shatter_prog * 350)
                sz = np.random.randint(6, 20)
                draw.rectangle([px, py, px + sz, py + sz], fill=(180, 180, 180, 200))

    # =========================================================================
    # SCENE 2: 11.5s - 17.0s | PIXELPIE EMBLEM & BRAND REVEAL
    # =========================================================================
    elif t < 17.0:
        anim_p = min(1.0, (t - 11.5) / 1.2)
        # Glowing iridescent emblem
        draw.text((WIDTH // 2 - 250, HEIGHT // 2 - 120), "PIXELPIE MEDIA", font=FONT_SUBTITLE, fill=(160, 175, 195, 240))
        draw.text((WIDTH // 2 - 420, HEIGHT // 2 - 40), "SHANTO DOWNLOAD MANAGER", font=FONT_HERO, fill=(0, 229, 255, 255))
        
        # Subtitle pill
        draw_rounded_rect(draw, [WIDTH // 2 - 260, HEIGHT // 2 + 70, WIDTH // 2 + 260, HEIGHT // 2 + 120], radius=25, fill=(25, 30, 42, 220), outline=(0, 229, 255, 80))
        draw.text((WIDTH // 2 - 230, HEIGHT // 2 + 82), "RE-ENGINEERED FOR ULTRA-HIGH SPEED", font=FONT_MONO_SM, fill=(0, 255, 157, 240))

    # =========================================================================
    # SCENE 3: 17.0s - 23.0s | SDM SLEEK WORKSPACE & HUD SHOWCASE
    # =========================================================================
    elif t < 23.0:
        draw.text((WIDTH // 2 - 380, 110), "Sleek. Obsidian Dark Glass. Pure Speed.", font=FONT_TITLE, fill=(245, 248, 252, 255))
        
        # Draw Main Workspace Glass Card
        card_w, card_h = 1300, 620
        cx0, cy0 = (WIDTH - card_w) // 2, 200
        draw_rounded_rect(draw, [cx0, cy0, cx0 + card_w, cy0 + card_h], radius=16, fill=(18, 22, 30, 230), outline=(255, 255, 255, 25), width=2)
        
        # Workspace Header
        draw_rounded_rect(draw, [cx0 + 20, cy0 + 20, cx0 + card_w - 20, cy0 + 80], radius=8, fill=(25, 31, 44, 200))
        draw.text((cx0 + 40, cy0 + 38), "⚡ ACTIVE DOWNLOADS // TELEMETRY HUB", font=FONT_MONO, fill=(0, 229, 255, 255))
        draw.text((cx0 + card_w - 380, cy0 + 38), "TOTAL SPEED: 94.8 MB/s", font=FONT_MONO, fill=(0, 255, 157, 255))
        
        # Download items
        sample_tasks = [
            ("Cyberpunk_Edgerunners_Ep01_4K.mkv", "Video", "8.4 GB", "DOWNLOADING", 0.68, "48.2 MB/s"),
            ("ArchLinux_x86_64_Kernel_Build.iso", "Compressed", "2.1 GB", "DOWNLOADING", 0.85, "46.6 MB/s"),
            ("DesignMonks_Asset_Library_2026.zip", "Documents", "540 MB", "COMPLETED", 1.0, "0 B/s"),
        ]
        
        for idx, (fname, cat, sz, stat, prog, spd) in enumerate(sample_tasks):
            ty = cy0 + 110 + idx * 150
            draw_rounded_rect(draw, [cx0 + 30, ty, cx0 + card_w - 30, ty + 125], radius=10, fill=(24, 29, 40, 220), outline=(255, 255, 255, 15))
            draw.text((cx0 + 50, ty + 18), fname, font=FONT_SUBTITLE, fill=(255, 255, 255, 255))
            draw.text((cx0 + card_w - 240, ty + 22), stat, font=FONT_MONO_SM, fill=(0, 255, 157, 255) if stat == "COMPLETED" else (0, 229, 255, 255))
            
            # Progress bar
            bar_w = card_w - 100
            draw_rounded_rect(draw, [cx0 + 50, ty + 68, cx0 + 50 + bar_w, ty + 82], radius=4, fill=(40, 46, 60, 255))
            draw_rounded_rect(draw, [cx0 + 50, ty + 68, cx0 + 50 + int(bar_w * prog), ty + 82], radius=4, fill=(0, 229, 255, 255) if stat != "COMPLETED" else (0, 255, 157, 255))
            
            draw.text((cx0 + 50, ty + 92), f"Size: {sz}  |  Speed: {spd}  |  Dynamic Slices: 16 threads", font=FONT_MONO_SM, fill=(140, 150, 165, 220))

    # =========================================================================
    # SCENE 4: 23.0s - 37.0s | COMPARISON: TRADITIONAL VS SDM SEQUENTIAL
    # =========================================================================
    elif t < 37.0:
        draw.text((WIDTH // 2 - 420, 90), "The Superpower: Sequential Pipelining", font=FONT_TITLE, fill=(245, 248, 252, 255))
        
        col_w = 640
        # Left Box: Traditional IDM
        lx0 = 140
        draw_rounded_rect(draw, [lx0, 180, lx0 + col_w, 820], radius=14, fill=(18, 20, 28, 230), outline=(255, 60, 60, 60), width=2)
        draw.text((lx0 + 30, 210), "TRADITIONAL CHUNKING (IDM)", font=FONT_SUBTITLE, fill=(255, 100, 100, 255))
        draw.text((lx0 + 30, 260), "Scatters random pieces across entire file.\nVideo player cannot read index. Must wait 100%.", font=FONT_MONO_SM, fill=(180, 190, 205, 200))
        
        # Fragmented progress blocks
        for b_idx in range(8):
            by = 350 + b_idx * 48
            draw_rounded_rect(draw, [lx0 + 30, by, lx0 + col_w - 30, by + 34], radius=6, fill=(30, 35, 48, 255))
            # Random incomplete fills
            fill_pct = [0.4, 0.9, 0.1, 0.7, 0.3, 0.8, 0.2, 0.6][b_idx]
            fw = int((col_w - 60) * fill_pct)
            draw_rounded_rect(draw, [lx0 + 30, by, lx0 + 30 + fw, by + 34], radius=6, fill=(255, 120, 80, 200))
        
        draw_rounded_rect(draw, [lx0 + 40, 740, lx0 + col_w - 40, 790], radius=8, fill=(40, 20, 20, 255), outline=(255, 80, 80, 120))
        draw.text((lx0 + 120, 755), "❌ UNPLAYABLE UNTIL 100%", font=FONT_MONO, fill=(255, 80, 80, 255))
        
        # Right Box: SDM Sequential Sliding Window
        rx0 = WIDTH - 140 - col_w
        draw_rounded_rect(draw, [rx0, 180, rx0 + col_w, 820], radius=14, fill=(18, 25, 35, 240), outline=(0, 229, 255, 100), width=2)
        draw.text((rx0 + 30, 210), "SDM SEQUENTIAL SLIDING WINDOW", font=FONT_SUBTITLE, fill=(0, 229, 255, 255))
        draw.text((rx0 + 30, 260), "Pulls Head (0.5s) + Tail (moov atom) first.\nThen streams contiguous blocks directly forward.", font=FONT_MONO_SM, fill=(180, 220, 240, 200))
        
        # Solid continuous stream representation
        seq_prog = min(1.0, max(0.05, (t - 23.0) / 13.0))
        
        # Head block (solid green)
        draw_rounded_rect(draw, [rx0 + 30, 350, rx0 + col_w - 30, 384], radius=6, fill=(0, 255, 157, 240))
        draw.text((rx0 + 45, 360), "BLOCK 1: CONTAINER HEAD (PREFETCHED IN 0.5s)", font=FONT_MONO_SM, fill=(0, 0, 0, 255))
        
        # Tail block (solid green)
        draw_rounded_rect(draw, [rx0 + 30, 400, rx0 + col_w - 30, 434], radius=6, fill=(0, 255, 157, 240))
        draw.text((rx0 + 45, 410), "TAIL BLOCK: MP4 MOOV ATOM (INDEX READY)", font=FONT_MONO_SM, fill=(0, 0, 0, 255))
        
        # Contiguous forward slices
        for s_idx in range(6):
            sy = 450 + s_idx * 45
            draw_rounded_rect(draw, [rx0 + 30, sy, rx0 + col_w - 30, sy + 34], radius=6, fill=(28, 38, 52, 255))
            # Consecutive fill from top down
            if seq_prog > (s_idx * 0.15):
                sub_f = min(1.0, (seq_prog - s_idx * 0.15) / 0.15)
                draw_rounded_rect(draw, [rx0 + 30, sy, rx0 + 30 + int((col_w - 60) * sub_f), sy + 34], radius=6, fill=(0, 229, 255, 255))
        
        draw_rounded_rect(draw, [rx0 + 40, 740, rx0 + col_w - 40, 790], radius=8, fill=(10, 40, 30, 255), outline=(0, 255, 157, 180))
        draw.text((rx0 + 100, 755), "✔ INSTANT 2-SECOND PLAYBACK", font=FONT_MONO, fill=(0, 255, 157, 255))

    # =========================================================================
    # SCENE 5: 37.0s - 46.5s | INSTANT 4K STREAMING IN ACTION
    # =========================================================================
    elif t < 46.5:
        draw.text((WIDTH // 2 - 410, 90), "Click Download. Watch in 2 Seconds.", font=FONT_TITLE, fill=(245, 248, 252, 255))
        
        # Media Player Viewport
        vw_w, vw_h = 1100, 600
        vx = (WIDTH - vw_w) // 2
        vy = 180
        draw_rounded_rect(draw, [vx, vy, vx + vw_w, vy + vw_h], radius=16, fill=(12, 16, 24, 255), outline=(0, 229, 255, 120), width=2)
        
        # Fake 4K movie frame: dynamic particle horizon
        p_frame = Image.new("RGBA", (vw_w - 8, vw_h - 60), (5, 8, 14, 255))
        pdraw = ImageDraw.Draw(p_frame)
        
        # Futuristic cyan horizon grid
        grid_y = (vw_h - 60) // 2 + 50
        pdraw.line([0, grid_y, vw_w, grid_y], fill=(0, 229, 255, 150), width=2)
        for gx in range(0, vw_w, 60):
            pdraw.line([gx, grid_y, int(gx * 1.5 - 200), vw_h - 60], fill=(0, 229, 255, 50))
        
        # Glowing sun in video
        pdraw.ellipse([vw_w // 2 - 80, grid_y - 120, vw_w // 2 + 80, grid_y + 40], fill=(255, 171, 0, 180))
        base.paste(p_frame, (vx + 4, vy + 4), p_frame)
        
        # Player Top Bar
        draw.text((vx + 30, vy + 20), "▶ STREAMING: Interstellar_IMAX_4K.mkv", font=FONT_SUBTITLE, fill=(255, 255, 255, 255))
        draw_rounded_rect(draw, [vx + vw_w - 200, vy + 15, vx + vw_w - 30, vy + 55], radius=6, fill=(0, 255, 157, 30), outline=(0, 255, 157, 180))
        draw.text((vx + vw_w - 180, vy + 24), "4K 60FPS • LIVE", font=FONT_MONO_SM, fill=(0, 255, 157, 255))
        
        # Player Bottom Controls
        draw_rounded_rect(draw, [vx, vy + vw_h - 60, vx + vw_w, vy + vw_h], radius=10, fill=(20, 26, 36, 255))
        draw.text((vx + 40, vy + vw_h - 42), "BUFFER LATENCY: 0.0s  //  DOWNLOAD PROGRESS: 4.8%  //  STREAM WIRE: 88 MB/s", font=FONT_MONO_SM, fill=(0, 229, 255, 240))

    # =========================================================================
    # SCENE 6: 46.5s - 56.7s | OPEN SOURCE GITHUB CTA & ONE-LINER INSTALL
    # =========================================================================
    else:
        draw.text((WIDTH // 2 - 320, 120), "Clean Downloads. Instant Playback.", font=FONT_TITLE, fill=(245, 248, 252, 255))
        
        # Hero Card
        hc_w, hc_h = 1100, 520
        hx = (WIDTH - hc_w) // 2
        hy = 230
        draw_rounded_rect(draw, [hx, hy, hx + hc_w, hy + hc_h], radius=18, fill=(18, 22, 32, 240), outline=(0, 229, 255, 80), width=2)
        
        draw.text((hx + 50, hy + 50), "SHANTO DOWNLOAD MANAGER (SDM)", font=FONT_HERO, fill=(0, 229, 255, 255))
        draw.text((hx + 55, hy + 140), "An Open-Source Innovation by PixelPie Media", font=FONT_SUBTITLE, fill=(200, 215, 235, 240))
        
        # One-line powershell box
        draw_rounded_rect(draw, [hx + 50, hy + 210, hx + hc_w - 50, hy + 300], radius=8, fill=(10, 12, 18, 255), outline=(255, 255, 255, 30))
        draw.text((hx + 75, hy + 230), "# Windows 1-Line Zero-Friction Install (PowerShell):", font=FONT_MONO_SM, fill=(120, 130, 150, 255))
        draw.text((hx + 75, hy + 260), "irm https://raw.githubusercontent.com/pikadexofc/shanto-download-manager/main/install.ps1 | iex", font=FONT_MONO, fill=(0, 255, 157, 255))
        
        # Badges
        draw_rounded_rect(draw, [hx + 50, hy + 340, hx + 360, hy + 410], radius=8, fill=(25, 35, 50, 200), outline=(0, 229, 255, 50))
        draw.text((hx + 75, hy + 362), "⭐ 100% Free & Open Source", font=FONT_MONO, fill=(255, 255, 255, 255))
        
        draw_rounded_rect(draw, [hx + 380, hy + 340, hx + 720, hy + 410], radius=8, fill=(25, 35, 50, 200), outline=(0, 229, 255, 50))
        draw.text((hx + 405, hy + 362), "🧩 Chrome Extension Ready", font=FONT_MONO, fill=(255, 255, 255, 255))
        
        draw.text((hx + 55, hy + 445), "github.com/pikadexofc/shanto-download-manager", font=FONT_MONO, fill=(0, 229, 255, 255))

    return base.convert("RGB")


def main():
    init_bg_cache()
    print(f"[Renderer] Initializing FFmpeg pipe for {TOTAL_FRAMES} frames ({TOTAL_DURATION}s)...")
    
    cmd = [
        "ffmpeg", "-y",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-s", f"{WIDTH}x{HEIGHT}",
        "-pix_fmt", "rgb24",
        "-r", str(FPS),
        "-i", "-",  # Video from stdin pipe
        "-i", AUDIO_PATH,  # Uploaded audio file
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        OUTPUT_MP4
    ]

    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    for i in range(TOTAL_FRAMES):
        frame = render_frame(i)
        raw_bytes = frame.tobytes()
        proc.stdin.write(raw_bytes)
        
        if i % 150 == 0 or i == TOTAL_FRAMES - 1:
            pct = (i / TOTAL_FRAMES) * 100
            print(f"[Renderer] Rendered {i}/{TOTAL_FRAMES} frames ({pct:.1f}%)...")

    proc.stdin.close()
    proc.wait()
    print(f"\n[DONE] Successfully rendered launch video to: {OUTPUT_MP4}")


if __name__ == "__main__":
    main()
