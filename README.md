# Clipper — local vertical-clip + caption tool

A free, watermark-free, runs-on-your-own-PC take on "Opus Clip". You find the
moment and give it timestamps; it cuts the clip, reframes it to vertical 9:16,
transcribes the speech locally, and burns in word-by-word highlighted captions.
Nothing leaves your machine.

There's a CLI (`clip.py`), a small Tkinter GUI (`clipper_gui.py`), and two
drag-and-drop `.bat` launchers for Windows.

## What it uses

- **ffmpeg** — cutting, reframing, burning captions
- **[faster-whisper](https://github.com/SYSTRAN/faster-whisper)** — local speech-to-text
- **yt-dlp** — optional; fetches a YouTube URL once and caches it locally

## Setup

Requires Python 3.10+ and `ffmpeg` on your PATH.

```bat
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
winget install Gyan.FFmpeg       :: if you don't have ffmpeg yet
```

The first run downloads the Whisper model you pick (~500 MB for `small.en`)
into `.cache\`.

## Usage

```
clip SOURCE START END [options]
```

`SOURCE` is a local video file **or** a YouTube URL. Timestamps accept `SS`,
`MM:SS` or `HH:MM:SS` (e.g. `18:42` or `1:02:30`, optional `.5`).

```
clip talk.mp4 18:42 19:15
clip "https://youtu.be/XXXX" 1:02:30 1:03:10 --model medium.en
clip talk.mp4 18:42 19:15 --reframe crop --font "Bebas Neue"
```

Finished clips land in `clips\`. Double-click **`Clipper GUI.bat`** for the
windowed version.

### Subtitle-only mode

Omit the timestamps and it keeps the video exactly as-is (any size, any aspect
ratio) and only burns in captions:

```
clip myvideo.mp4
```

Or drag a video onto **`subs.bat`**. Output is `clips\<name>_subtitled.mp4`.
Fully offline.

- Non-English audio: `--model small` (auto-detects language) or `--model large-v3`.
- Bigger/smaller captions: `--fontsize 120`; move them up: `--marginv 400`.

## Options

| Option | Default | What it does |
|---|---|---|
| `--reframe blur\|crop\|none` | `blur` | `blur` keeps the whole frame with a blurred fill (never crops out a speaker); `crop` zooms to fill |
| `--model base.en\|small.en\|medium.en\|large-v3` | `small.en` | Bigger = more accurate captions, slower. `medium.en` is a good balance |
| `--device cpu\|cuda` | `cpu` | `cuda` is much faster on an NVIDIA GPU but needs cuDNN installed |
| `--font "Name"` | `Arial Black` | Caption font. Install **Bebas Neue** for the classic clip look |
| `--fontsize N` | `96` | Caption size |
| `--marginv N` | `300` | Distance of captions from the bottom |
| `--no-captions` | off | Skip captions entirely |

## How it works

1. **Get the segment** — `ffmpeg -ss/-to` on a local file. For a URL, yt-dlp
   downloads the full video once (≤1080p, h264) into `.cache\` keyed by video
   id, so every later clip from the same video is instant and offline.
2. **Reframe** — for `blur`, the source is scaled to fill 1080×1920, blurred,
   and the original frame is overlaid centred on top; for `crop`, it's scaled
   and centre-cropped.
3. **Transcribe** — faster-whisper with `word_timestamps=True` gives a start/end
   for every word.
4. **Caption** — words are grouped into short chunks (max 5 words, new chunk
   after a 0.6 s pause) and written as an ASS subtitle file: one `Dialogue`
   line per word, showing the whole chunk with just the current word in the
   highlight colour. ffmpeg burns that in with `subtitles=`.

Colours, words-per-line and highlight style are constants near the top of
`clip.py` (`BASE_COLOR`, `HL_COLOR`, `MAX_WORDS`).

## A note on YouTube downloads

YouTube throttles direct downloads unless yt-dlp solves its anti-bot challenge
(`--remote-components ejs:github`, which runs remote JS). If URL mode is slow,
download the full video once with any tool you trust and clip from the local
file — that path has no throttling and works offline.

## License

MIT — see [LICENSE](LICENSE).
