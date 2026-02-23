<p align="center">
  <img src="images/logo-full-for-black-background.png" alt="Meeting AI Analyser" width="400">
</p>

<p align="center">
  <strong>Real-time transcription & AI analysis of your meetings, 100% local</strong><br>
  System audio capture + microphone · Local Whisper · Claude AI analysis
</p>

<p align="center">
  <a href="#installation">Installation</a> · <a href="#usage">Usage</a> · <a href="#configuration">Configuration</a>
</p>

---

Captures system audio (WASAPI loopback) and microphone, transcribes locally via Whisper, and automatically analyzes content with Claude AI. Real-time web interface at `http://localhost:5555`.

---

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Usage](#usage)
- [Web Interface](#web-interface)
- [Configuration](#configuration)
- [Project Files](#project-files)
- [Server API](#server-api)
- [Technical Details](#technical-details)
- [Troubleshooting](#troubleshooting)

---

## Features

### Real-time Transcription

- Simultaneous capture of **system audio** (Teams, Zoom, browser...) and **microphone**
- Local transcription via **faster-whisper** (no data sent externally)
- GPU support (CUDA) for accelerated transcription, automatic CPU fallback
- Silence detection (VAD) to skip pauses
- Smart deduplication between consecutive segments

### Automatic AI Analysis

- Meeting analysis every 60 seconds via **Claude Code CLI**
- Structured Markdown summary:
  - Topics discussed
  - Decisions made
  - Open questions
  - Suggested technical solutions
  - Action items (who does what)
- Only triggers when transcription changes

### Web Interface

- Split-panel dashboard (transcription on the left, analysis on the right)
- Real-time streaming via Server-Sent Events (SSE)
- Automatic fallback polling if SSE fails
- Smart auto-scroll (pauses if user scrolls manually)
- Connection indicator (green/red)
- Segment counter and timestamp
- Reset button to start fresh
- Dark theme (GitHub-like)
- Markdown rendering for analysis

---

## Architecture

```
+-------------------+     +-------------------+     +-------------------+
|  Audio Hardware   |     |   analyst.py      |     |   index.html      |
|  (System + Mic)   |     |  AI Analysis      |     |  Web Interface    |
+--------+----------+     +--------+----------+     +--------+----------+
         |                         |                          |
         v                         v                          v
+-------------------+     +-------------------+     +-------------------+
| live_transcribe.py|---->| analyse_reunion.md|<----| server.py (Flask) |
| Capture + Whisper |     | Analysis result   |     | API + SSE         |
+--------+----------+     +-------------------+     +--------+----------+
         |                                                    ^
         v                                                    |
+-------------------+                                         |
|transcription_     |---------------------------------------->+
|   live.txt        |    Read by server.py via /api/stream
+-------------------+
```

### Data Flow

1. **`live_transcribe.py`** captures audio in 10s segments, transcribes via Whisper, writes to `transcription_live.txt`
2. **`analyst.py`** reads `transcription_live.txt` every 60s, sends to Claude, writes results to `analyse_reunion.md`
3. **`server.py`** monitors both files and exposes them via REST API + SSE
4. **`index.html`** connects via SSE and displays updates in real-time

---

## Prerequisites

### Required

| Dependency         | Version                  | Purpose                        |
| ------------------ | ------------------------ | ------------------------------ |
| **Python**         | 3.10+ (tested with 3.13) | Runtime                        |
| **faster-whisper** | latest                   | Speech-to-text transcription   |
| **pyaudiowpatch**  | latest                   | WASAPI audio capture (Windows) |
| **numpy**          | latest                   | Audio processing               |
| **scipy**          | latest                   | Audio resampling               |
| **flask**          | latest                   | Web server                     |
| **psutil**         | latest                   | Process management             |

### Optional

| Dependency                  | Purpose                                   |
| --------------------------- | ----------------------------------------- |
| **NVIDIA GPU + CUDA 11.8+** | Accelerated transcription (5-10x faster)  |
| **Claude Code CLI**         | AI meeting analysis (`analyst.py` module) |

### System

- **Windows 10/11** only (WASAPI loopback is a Windows API)
- An active **audio output device** (for loopback)
- A **microphone** (optional, can be disabled with `--no-mic`)

---

## Installation

### 1. Install Python dependencies

```bash
pip install faster-whisper pyaudiowpatch numpy scipy flask psutil
```

### 2. (Optional) NVIDIA GPU support

If you have a CUDA-compatible NVIDIA card:

```bash
pip install nvidia-cublas-cu11 nvidia-cudnn-cu11
```

The script automatically detects GPU availability and falls back to CPU if needed.

### 3. (Optional) Install Claude Code CLI

For automatic AI meeting analysis:

```bash
npm install -g @anthropic-ai/claude-code
```

Without Claude Code, transcription works normally but without analysis.

### 4. First launch

On first launch, Whisper automatically downloads the chosen model (~500 MB for `small`). This download only occurs once.

---

## Usage

### Method 1: Single entry point (recommended)

```bash
python main.py
```

This will:

1. Start the web server
2. Open the browser automatically
3. Load Whisper and start transcription
4. Start Claude AI analysis (if available)

All modules run as threads in a single process. Close the browser tab to shut everything down (heartbeat auto-shutdown).

### Method 2: Portable executable

Double-click **`MeetingAIAnalyser.exe`** (if built with PyInstaller). Same behavior as `python main.py`.

### Method 3: Manual launch (3 terminals)

```bash
# Terminal 1: Transcription
python live_transcribe.py

# Terminal 2: AI analysis (wait ~8s for Whisper to load)
python analyst.py

# Terminal 3: Web server
python server.py
```

Then open `http://localhost:5555`.

---

## Web Interface

The interface is available at `http://localhost:5555` and consists of:

### Header

- **Green pulsing dot**: SSE connection active
- **Red static dot**: connection lost
- **Reset button**: clears transcription and analysis, starts fresh
- **Segment counter**: number of transcribed segments
- **Timestamp**: last update received

### Left Panel: Transcription

- Displays each segment with its timestamp `[HH:MM:SS]`
- The last 3 segments are highlighted in blue
- Auto-scroll to bottom (pauses if you scroll manually)

### Right Panel: Claude Analysis

- Structured meeting summary in Markdown
- Automatically updated every 60s
- Renders: headings, lists, bold, italic, code

### Stopping

- **Stop button** or **closing the browser tab**: sends a shutdown signal to all processes
- **Ctrl+C** in console if launched manually

---

## Configuration

### Command-line options

```
python main.py [OPTIONS]
```

| Option            | Default | Description                                                  |
| ----------------- | ------- | ------------------------------------------------------------ |
| `--port N`        | 5555    | Web server port                                              |
| `--no-mic`        | false   | Disable microphone capture (loopback only)                   |
| `--mic-device ID` | auto    | Microphone device index to use                               |
| `--segment N`     | 10      | Segment duration in seconds                                  |
| `--model SIZE`    | small   | Whisper model: `tiny`, `base`, `small`, `medium`, `large-v3` |
| `--language LANG` | fr      | ISO language code (fr, en, de, es...)                        |
| `--no-analysis`   | false   | Disable Claude AI analysis                                   |
| `--no-browser`    | false   | Don't open browser automatically                             |

### Whisper Model Selection

| Model      | Size   | GPU RAM | Quality   | Speed     |
| ---------- | ------ | ------- | --------- | --------- |
| `tiny`     | 39 MB  | ~1 GB   | Basic     | Very fast |
| `base`     | 74 MB  | ~1 GB   | Decent    | Fast      |
| `small`    | 244 MB | ~2 GB   | Good      | Medium    |
| `medium`   | 769 MB | ~5 GB   | Very good | Slow      |
| `large-v3` | 1.5 GB | ~10 GB  | Excellent | Very slow |

> **Recommendation:** `small` offers the best quality/speed tradeoff for most languages.

### Internal Parameters

| Parameter                  | File               | Value | Description                  |
| -------------------------- | ------------------ | ----- | ---------------------------- |
| `DEFAULT_SEGMENT_DURATION` | live_transcribe.py | 10    | Segment duration (seconds)   |
| `SILENCE_THRESHOLD`        | live_transcribe.py | 0.001 | RMS silence threshold        |
| `SAMPLE_RATE`              | live_transcribe.py | 16000 | Sampling frequency           |
| `interval`                 | analyst.py         | 60    | Analysis frequency (seconds) |
| `port`                     | server.py          | 5555  | Web server port              |

---

## Project Files

### Source Code

| File                 | Lines | Role                                         |
| -------------------- | ----- | -------------------------------------------- |
| `main.py`            | 128   | Single entry point, thread orchestration     |
| `live_transcribe.py` | 477   | Audio capture engine + Whisper transcription |
| `server.py`          | 226   | Flask web server (REST API + SSE)            |
| `analyst.py`         | 142   | AI analysis module via Claude CLI            |
| `index.html`         | 550+  | Web interface (HTML + CSS + JS embedded)     |

### Build Files

| File            | Role                                   |
| --------------- | -------------------------------------- |
| `build.spec`    | PyInstaller configuration              |
| `build_icon.py` | Converts logo to multi-resolution .ico |

### Generated Files (runtime)

| File                       | Role                                   |
| -------------------------- | -------------------------------------- |
| `transcription_live.txt`   | Full timestamped transcription         |
| `transcription_latest.txt` | Latest transcribed segment only        |
| `analyse_reunion.md`       | Latest Claude analysis in Markdown     |
| `temp_segment.wav`         | Temporary audio file (auto-deleted)    |
| `temp_prompt.txt`          | Temporary Claude prompt (auto-deleted) |

---

## Server API

The Flask server exposes the following endpoints on `http://localhost:5555`:

### `GET /`

Serves the web interface (`index.html`).

### `GET /api/transcription`

Returns the current transcription.

```json
{
  "content": "[08:30:15] Hello, let's get started...\n[08:30:25] Yes, first topic...",
  "mtime": 1708700000.123
}
```

### `GET /api/analysis`

Returns the current Claude analysis.

```json
{
  "content": "# Meeting Analysis - 2026-02-23 10:30\n\n## Topics Discussed\n...",
  "mtime": 1708700060.456
}
```

### `GET /api/stream`

SSE (Server-Sent Events) endpoint. Sends events when transcription or analysis changes.

```
data: {"type": "transcription", "content": "..."}
data: {"type": "analysis", "content": "..."}
```

Check interval: 2 seconds.

### `GET /api/devices`

Returns available microphone devices and the currently active one.

```json
{
  "devices": [{ "id": 1, "name": "Microphone (Realtek)", "channels": 2, "sampleRate": 48000 }],
  "active": 1
}
```

### `POST /api/restart`

Restarts transcription with a new microphone device.

```json
{ "micDevice": 5 }
```

### `POST /api/reset`

Resets transcription and analysis. Returns `{"status": "reset"}`.

### `GET /api/stop`

Stops all Meeting AI Analyser processes. Returns `{"status": "stopped"}`.

### `GET /api/status`

Returns the application loading status.

```json
{
  "server": true,
  "whisper": false,
  "transcription": false,
  "analysis": false,
  "ready": false,
  "message": "Loading Whisper model..."
}
```

### `GET /api/heartbeat`

Browser heartbeat ping. If no ping received for 15s, the server auto-shuts down.

---

## Technical Details

### Audio Capture

- **WASAPI Loopback**: captures all system audio output (what you hear in your headphones/speakers)
- **Microphone**: captures via default input device or a specified device
- Both streams are converted to **mono 16kHz** (format required by Whisper) then **mixed** together
- Automatic **normalization** if signal exceeds 95% to prevent clipping
- **Threading**: each audio source has its own thread-safe callback with lock

### Whisper Transcription

- **Beam search**: size 5 (quality/speed tradeoff)
- **VAD** (Voice Activity Detection) enabled: skips silent segments
- **Min silence**: 500ms (cutoff threshold)
- **Speech padding**: 300ms (margin around detected speech)
- The model is loaded once at startup, segments are transcribed on the fly

### Deduplication

Prevents repetitions between consecutive segments:

1. Compares the last N words of the previous segment with the first N of the new one
2. If overlap >= 5 words, removes the duplicated portion from the new segment
3. Case-insensitive comparison, max 20 words checked

### GPU Detection

At startup, the script tries in order:

1. **CUDA float16** (NVIDIA GPU) - maximum performance
2. **CPU int8** (fallback) - works everywhere, slower

The NVIDIA DLL path is automatically added to PATH (specific to Python 3.13 Windows Store).

### Claude Analysis

- Uses `claude --print` in non-interactive mode
- The prompt is written to a temporary file to avoid Windows quoting issues
- Timeout: 120 seconds
- Only triggers if:
  - The transcription has changed since the last analysis
  - The content exceeds 50 characters

---

## Troubleshooting

### "No WASAPI loopback device found"

- Make sure an audio output device is active (headphones, speakers, virtual output)
- On some systems, WASAPI loopback is only available when audio is playing

### "Module faster_whisper not found"

```bash
pip install faster-whisper
```

### Transcription is slow (CPU)

- Install NVIDIA drivers + CUDA to use the GPU
- Or use a lighter model: `--model tiny` or `--model base`

### "'claude' not found in PATH"

- Install Claude Code CLI: `npm install -g @anthropic-ai/claude-code`
- Or run without the analyst.py module (transcription only)

### Web interface doesn't load

- Check that `server.py` is running and listening on port 5555
- Check that no other process is using the port: `netstat -ano | findstr 5555`

### Microphone not detected

- List devices: `python live_transcribe.py --list-devices`
- Select manually: `python live_transcribe.py --mic-device ID`

### Transcription contains repetitions

- Increase segment duration: `--segment 15` or `--segment 20`
- The deduplication mechanism handles most cases, but very short segments may generate duplicates

---

## License

MIT License. See LICENSE file for details.
