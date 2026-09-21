# Clipper

Opus Clip and the other "turn your long video into shorts" tools charge a
subscription, stamp a watermark on the free tier, and upload your footage to
someone else's server. All I wanted was the boring part done for me. I already
know which moment is good. Clipper takes a video and two timestamps, cuts the
clip, reframes it to vertical 9:16, transcribes the speech on my own machine,
and burns in captions that highlight each word as it's spoken. It's free and
nothing leaves the PC.

There's a command line (`clip.py`), a small Tkinter window (`clipper_gui.py`)
and two `.bat` files you can drag videos onto.

## What it's built on

ffmpeg does the cutting, reframing and caption burn-in.
[faster-whisper](https://github.com/SYSTRAN/faster-whisper) does the
speech-to-text locally. yt-dlp is optional and only used if you hand it a
YouTube URL instead of a file.

## Setup

You need Python 3.10 or newer and ffmpeg on your PATH.

```bat
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
winget install Gyan.FFmpeg       :: skip if you already have ffmpeg
```

The first run downloads the Whisper model you asked for into `.cache\`. The
default, `small.en`, is about 500 MB.

## Usage

```
clip SOURCE START END [options]
```

`SOURCE` is a local video file or a YouTube URL. Timestamps can be `SS`,
`MM:SS` or `HH:MM:SS`, with an optional `.5` on the end.

```
clip talk.mp4 18:42 19:15
clip "https://youtu.be/XXXX" 1:02:30 1:03:10 --model medium.en
clip talk.mp4 18:42 19:15 --reframe crop --font "Bebas Neue"
```

Clips land in `clips\`. Double-click `Clipper GUI.bat` if you'd rather have a
window.

### Just captions, no cutting

Leave out the timestamps and Clipper keeps the video exactly as it is, any size,
any aspect ratio, and only burns in captions.

```
clip myvideo.mp4
```

Or drag a video onto `subs.bat`. The output is `clips\<name>_subtitled.mp4`.
This mode never touches the internet.

For non-English audio use `--model small` (it auto-detects the language) or
`--model large-v3`. `--fontsize 120` makes the captions bigger and
`--marginv 400` moves them further up the frame.

## Options

| Option | Default | What it does |
|---|---|---|
| `--reframe blur\|crop\|none` | `blur` | `blur` keeps the whole frame on a blurred background, so nobody gets cropped out of a two-person shot. `crop` zooms in to fill the frame. |
| `--model base.en\|small.en\|medium.en\|large-v3` | `small.en` | Bigger models are more accurate and slower. `medium.en` is the sweet spot on a CPU. |
| `--device cpu\|cuda` | `cpu` | `cuda` is much faster on an NVIDIA card but needs cuDNN installed. |
| `--font "Name"` | `Arial Black` | Caption font. Bebas Neue gives the look every viral clip seems to use. |
| `--fontsize N` | `96` | Caption size. |
| `--marginv N` | `300` | Distance from the bottom edge. |
| `--no-captions` | off | Skip captions. |

## How it works

For a local file, ffmpeg cuts the range with `-ss` and `-to`. For a URL,
yt-dlp downloads the whole video once (1080p or lower, h264) into `.cache\`,
named by video id, so the second clip from the same video is instant and
offline.

Reframing to 9:16 in `blur` mode scales the source up to fill 1080x1920, blurs
it, and overlays the original frame centred on top. `crop` mode scales and
centre-crops instead.

faster-whisper runs with `word_timestamps=True`, so every word comes back with
a start and end time. Clipper groups those into chunks of up to five words,
starting a new chunk after any pause longer than 0.6 seconds. It writes an ASS
subtitle file with one `Dialogue` line per word. Each line shows the whole
chunk, with only the current word in the highlight colour. ffmpeg then burns
that file in with the `subtitles=` filter.

The colours, the words-per-chunk limit and the pause threshold are constants
near the top of `clip.py` (`BASE_COLOR`, `HL_COLOR`, `MAX_WORDS`, `GAP_BREAK`).

## YouTube downloads are slow sometimes

YouTube throttles yt-dlp unless it solves an anti-bot challenge, which needs
`--remote-components ejs:github` and a JS runtime (deno). Clipper passes the
flag, but if URL mode is crawling, the easy fix is to download the video once
with whatever tool you like and clip from the local file. That path is never
throttled.

## License

MIT, see [LICENSE](LICENSE).
