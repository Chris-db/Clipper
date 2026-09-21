#!/usr/bin/env python3
"""
clip.py - A free, local, watermark-free "Opus Clip"-style tool.

You provide the video (a local file OR a YouTube URL) and a start/end timestamp.
It produces a vertical 9:16 clip with auto-generated, word-by-word highlighted
captions burned in. The moment-finding is your job; the boring parts are mine.

Usage:
    py clip.py SOURCE [START END] [options]

Examples:
    py clip.py myvideo.mp4                    # just subtitle your own video, kept exactly as-is
    py clip.py debate.mp4 18:42 19:15         # cut + reframe to 9:16 + subtitle
    py clip.py "https://youtu.be/XXXX" 1:02:30 1:03:10 --model medium.en
    py clip.py debate.mp4 18:42 19:15 --reframe crop --font "Bebas Neue"

Timestamps accept: SS | MM:SS | HH:MM:SS  (optional .ms, e.g. 18:42.5)
Omit START/END to subtitle the whole file without cutting or reframing.
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Windows consoles default to cp1252 and choke on non-Latin-1 output; force UTF-8.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent
CLIPS_DIR = ROOT / "clips"
CACHE_DIR = ROOT / ".cache"

CANVAS_W, CANVAS_H = 1080, 1920

# Caption look (tweak to taste)
BASE_COLOR = r"&HFFFFFF&"   # white  (ASS is BBGGRR)
HL_COLOR = r"&H00FFFF&"     # yellow highlight for the word being spoken
MAX_WORDS = 5               # words per caption chunk
GAP_BREAK = 0.6             # start a new chunk after a pause this long (seconds)


# On Windows, keep child processes (ffmpeg/yt-dlp) from popping up console windows
# when this is driven by a GUI (pythonw). Harmless on the command line / other OSes.
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def run(cmd, **kw):
    print("·", " ".join(str(c) for c in cmd))
    return subprocess.run(cmd, check=True, creationflags=CREATE_NO_WINDOW, **kw)


def parse_ts(s):
    s = s.strip()
    if re.fullmatch(r"\d+(\.\d+)?", s):
        return float(s)
    sec = 0.0
    for p in s.split(":"):
        sec = sec * 60 + float(p)
    return sec


def fmt_ass(sec):
    sec = max(0.0, sec)
    cs = int(round(sec * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def probe_dims(path):
    out = subprocess.check_output(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "csv=p=0:s=x", str(path)],
        text=True, creationflags=CREATE_NO_WINDOW).strip()
    w, h = out.replace("\n", "x").split("x")[:2]
    return int(w), int(h)


def probe_duration(path):
    out = subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)], text=True, creationflags=CREATE_NO_WINDOW).strip()
    return float(out)


def ensure_deno():
    """Make sure deno (yt-dlp's JS challenge-solver runtime) is reachable on PATH."""
    if shutil.which("deno"):
        return
    import glob
    cands = glob.glob(os.path.join(os.environ.get("LOCALAPPDATA", ""),
                                   r"Microsoft\WinGet\Packages\DenoLand.Deno*\deno.exe"))
    cands += glob.glob(os.path.join(os.path.expanduser("~"), r".deno\bin\deno.exe"))
    for c in cands:
        if os.path.exists(c):
            os.environ["PATH"] = os.path.dirname(c) + os.pathsep + os.environ.get("PATH", "")
            return


def download_cached(url):
    """Download the full video once (<=1080p, throttle-solver on) and cache it by video id.
    Avoids ffmpeg remote-seek entirely; future clips from the same video reuse the cache."""
    ensure_deno()
    CACHE_DIR.mkdir(exist_ok=True)
    keep = (".mp4", ".mkv", ".webm")
    m = re.search(r"(?:v=|youtu\.be/|/shorts/|/embed/)([A-Za-z0-9_-]{11})", url)
    vid = m.group(1) if m else None
    if vid:
        existing = [f for f in CACHE_DIR.glob(f"{vid}.*") if f.suffix.lower() in keep]
        if existing:
            print(f"· using cached video: {existing[0].name}")
            return existing[0]
    print("· downloading full video (one-time per video; future clips reuse it) ...")
    run([sys.executable, "-m", "yt_dlp", "--remote-components", "ejs:github",
         "-f", "bv*[height<=1080]+ba/b[height<=1080]/b", "-S", "vcodec:h264",
         "--merge-output-format", "mp4",
         "-o", str(CACHE_DIR / "%(id)s.%(ext)s"), url])
    pool = CACHE_DIR.glob(f"{vid}.*") if vid else CACHE_DIR.glob("*")
    files = sorted((f for f in pool if f.suffix.lower() in keep),
                   key=lambda p: p.stat().st_mtime)
    if not files:
        sys.exit("Download failed - check the URL / your connection.")
    return files[-1]


def get_segment(source, start, end, workdir):
    """Cut [start, end] to workdir/segment.mp4 (re-encoded). Omit both to use the whole file."""
    seg = workdir / "segment.mp4"
    src = download_cached(source) if re.match(r"^https?://", source) else Path(source)
    if not src.exists():
        sys.exit(f"File not found: {src}")
    if start is None:
        start = 0.0
    if end is None:
        end = probe_duration(src)
    dur = max(0.1, end - start)
    run(["ffmpeg", "-y", "-ss", f"{start:.3f}", "-i", str(src), "-t", f"{dur:.3f}",
         "-c:v", "libx264", "-c:a", "aac", str(seg)])
    return seg


def transcribe(seg, model_name, device, compute_type):
    from faster_whisper import WhisperModel
    print(f"· transcribing with faster-whisper [{model_name}] on {device} ...")
    model = WhisperModel(model_name, device=device, compute_type=compute_type)
    segments, _ = model.transcribe(str(seg), word_timestamps=True, beam_size=5,
                                   vad_filter=True)
    words = []
    for s in segments:
        for w in (s.words or []):
            t = w.word.strip()
            if t:
                words.append((float(w.start), float(w.end), t))
    return words


def chunk_words(words):
    chunks, cur = [], []
    for i, (ws, we, wt) in enumerate(words):
        if cur and (len(cur) >= MAX_WORDS or ws - cur[-1][1] > GAP_BREAK):
            chunks.append(cur)
            cur = []
        cur.append((ws, we, wt))
    if cur:
        chunks.append(cur)
    return chunks


def build_ass(words, ass_path, font, fontsize, marginv, play_w=CANVAS_W, play_h=CANVAS_H):
    # Caption sizing is tuned for a 1920-tall canvas; scale it for other resolutions.
    scale = play_h / 1920.0
    fontsize = max(12, round(fontsize * scale))
    marginv = max(10, round(marginv * scale))
    margin_lr = max(16, round(80 * scale))
    outline = max(2, round(6 * scale))
    shadow = max(1, round(2 * scale))
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {play_w}
PlayResY: {play_h}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font},{fontsize},&H00FFFFFF,&H000000FF,&H00000000,&H64000000,1,0,0,0,100,100,0,0,1,{outline},{shadow},2,{margin_lr},{margin_lr},{marginv},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, Effect, Text
"""
    lines = [header]
    for chunk in chunk_words(words):
        for i, (ws, we, _) in enumerate(chunk):
            start = ws
            end = chunk[i + 1][0] if i + 1 < len(chunk) else we
            if end <= start:
                end = start + 0.15
            parts = []
            for j, (_, _, wt) in enumerate(chunk):
                safe = wt.replace("{", "(").replace("}", ")")
                safe = re.sub(r"^[\s,.;:!?]+", "", safe)  # drop stray leading punctuation on any word
                if j == i:
                    parts.append(r"{\c" + HL_COLOR + "}" + safe + r"{\c" + BASE_COLOR + "}")
                else:
                    parts.append(safe)
            text = re.sub(r"\s{2,}", " ", " ".join(parts)).strip()
            lines.append(f"Dialogue: 0,{fmt_ass(start)},{fmt_ass(end)},Default,,0,0,0,{text}")
    ass_path.write_text("\n".join(lines), encoding="utf-8")


def render(seg, out_path, reframe, workdir):
    """Reframe to 9:16 and burn the captions (subs.ass must be in workdir)."""
    if reframe == "blur":
        vf = ("[0:v]scale=1080:1920:force_original_aspect_ratio=increase,"
              "crop=1080:1920,boxblur=22:4,setsar=1[bg];"
              "[0:v]scale=1080:-2[fg];"
              "[bg][fg]overlay=(W-w)/2:(H-h)/2[base];"
              "[base]subtitles=subs.ass[v]")
    elif reframe == "crop":
        vf = ("[0:v]scale=1080:1920:force_original_aspect_ratio=increase,"
              "crop=1080:1920,setsar=1[base];[base]subtitles=subs.ass[v]")
    else:  # none -> keep original frame, just burn captions
        vf = "[0:v]subtitles=subs.ass[v]"
    out_tmp = workdir / "out.mp4"
    run(["ffmpeg", "-y", "-i", "segment.mp4", "-filter_complex", vf,
         "-map", "[v]", "-map", "0:a?", "-c:v", "libx264", "-preset", "veryfast",
         "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
         "out.mp4"], cwd=workdir)
    CLIPS_DIR.mkdir(exist_ok=True)
    shutil.move(str(out_tmp), str(out_path))


def main():
    ap = argparse.ArgumentParser(description="Free local Opus-Clip-style vertical clipper.")
    ap.add_argument("source", help="Local video path or YouTube URL")
    ap.add_argument("start", nargs="?", default=None,
                    help="Start timestamp (SS | MM:SS | HH:MM:SS). Omit to use the whole file.")
    ap.add_argument("end", nargs="?", default=None, help="End timestamp.")
    ap.add_argument("--out", help="Output file path (default: clips/<name>.mp4)")
    ap.add_argument("--reframe", choices=["blur", "crop", "none"], default=None,
                    help="blur=keep whole frame w/ blurred fill; crop=zoom to fill; "
                         "none=keep original size (just add subtitles). "
                         "Defaults to 9:16 blur when cutting, 'none' when subtitling a whole file.")
    ap.add_argument("--model", default="small.en",
                    help="faster-whisper model: base.en | small.en | medium.en | large-v3")
    ap.add_argument("--device", default="cpu", choices=["cpu", "cuda"],
                    help="cpu (reliable) or cuda (faster, needs cuDNN)")
    ap.add_argument("--font", default="Arial Black", help="Caption font name")
    ap.add_argument("--fontsize", type=int, default=96)
    ap.add_argument("--marginv", type=int, default=300, help="Caption distance from bottom")
    ap.add_argument("--no-captions", action="store_true")
    args = ap.parse_args()

    start = parse_ts(args.start) if args.start is not None else None
    end = parse_ts(args.end) if args.end is not None else None
    whole = start is None and end is None
    if start is not None and end is not None and end <= start:
        sys.exit("End must be after start.")

    # Default reframe: keep original size when subtitling a whole file, else 9:16 blur.
    reframe = args.reframe if args.reframe is not None else ("none" if whole else "blur")

    if args.out:
        out_path = Path(args.out)
    else:
        if re.match(r"^https?://", args.source):
            base = "clip"
        else:
            base = re.sub(r"[^A-Za-z0-9]+", "_", Path(args.source).stem)[:40] or "clip"
        out_path = CLIPS_DIR / (f"{base}_subtitled.mp4" if whole
                                else f"{base}_{int(start or 0)}-{int(end or 0)}.mp4")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    compute = "int8" if args.device == "cpu" else "float16"
    with tempfile.TemporaryDirectory() as td:
        workdir = Path(td)
        seg = get_segment(args.source, start, end, workdir)
        play_w, play_h = probe_dims(seg) if reframe == "none" else (CANVAS_W, CANVAS_H)
        if args.no_captions:
            (workdir / "subs.ass").write_text(
                "[Script Info]\nScriptType: v4.00+\n[Events]\n", encoding="utf-8")
        else:
            words = transcribe(seg, args.model, args.device, compute)
            if not words:
                print("! No speech detected - rendering without captions.")
            build_ass(words, workdir / "subs.ass", args.font, args.fontsize,
                      args.marginv, play_w, play_h)
        render(seg, out_path, reframe, workdir)

    print(f"\n[DONE] {out_path.resolve()}")


if __name__ == "__main__":
    main()
