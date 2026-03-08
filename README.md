# 🎵 Rhythm Hand Game

> A real-time, camera-based rhythm game where you hit beat-synced targets using only your bare hands — no mouse, no controller, just you and a webcam.

<br>

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Demo](#-demo)
- [How It Works](#-how-it-works)
  - [Hand Tracking](#1-hand-tracking)
  - [Beat-Accurate Spawning](#2-beat-accurate-spawning)
  - [Target Lifecycle](#3-target-lifecycle)
  - [Hit Detection](#4-hit-detection)
  - [Scoring System](#5-scoring-system)
- [Game States](#-game-states)
- [Project Structure](#-project-structure)
- [Requirements](#-requirements)
- [Installation](#-installation)
  - [Windows](#windows)
  - [Linux (Arch)](#linux-arch)
  - [macOS](#macos)
- [Running the Game](#-running-the-game)
- [Configuration & Tuning](#-configuration--tuning)
  - [BPM and Beat Offset](#bpm-and-beat-offset)
  - [Target Lifetime](#target-lifetime)
  - [Safe Distance Fallbacks](#safe-distance-fallbacks)
  - [Swapping the Song](#swapping-the-song)
- [Controls](#-controls)
- [Troubleshooting](#-troubleshooting)
  - [Targets not spawning on beat](#targets-not-spawning-on-beat)
  - [MediaPipe solutions error](#mediapipe-solutions-error)
  - [Pygame compiling from source](#pygame-compiling-from-source)
  - [Webcam not detected](#webcam-not-detected)
  - [Extra misses being counted](#extra-misses-being-counted)
- [Building an Executable](#-building-an-executable)
- [Known Limitations](#-known-limitations)
- [Future Ideas](#-future-ideas)
- [Tech Stack](#-tech-stack)
- [License](#-license)

---

## 🎮 Overview

Beat Tapper is inspired by games like **osu!** — except instead of clicking circles with a mouse, you physically reach out and touch targets on screen using your **index fingers**, tracked in real time through your webcam.

The game reads a song's BPM, calculates exactly when each beat will land, and spawns a target on screen `TARGET_LIFETIME` seconds **before** that beat. A shrinking white ring on each target acts as a visual countdown — when the ring disappears, the beat has arrived. Hit the target before it expires to score points.

The entire game runs in a single Python script using:
- **OpenCV** for rendering everything onto the camera feed
- **MediaPipe** for real-time hand landmark detection
- **Pygame** for audio playback and music clock synchronisation

No game engine. No external GUI framework. Just a webcam window and your hands.

---

## 📹 Demo

Game over screen example:

```
GAME OVER
Final Score: 370
Shown:       45
Hit:         41   ← green
Missed:       4   ← red
Accuracy:  91.1%
```

---

## 🧠 How It Works

### 1. Hand Tracking

Every frame, the webcam image is passed through **MediaPipe's hand landmark model**. MediaPipe detects up to **2 hands** and returns 21 landmarks per hand. The game uses only **Landmark #8** from each hand — the tip of the index finger.

```
Landmark indices (MediaPipe):
  0  = wrist
  4  = thumb tip
  8  = index finger tip   ← used by this game
  12 = middle finger tip
  16 = ring finger tip
  20 = pinky tip
```

The (x, y) pixel coordinates of each detected fingertip are extracted each frame and used as the player's cursor(s). They're rendered as cyan dots on the video feed so you can see exactly where the game thinks your finger is.

---

### 2. Beat-Accurate Spawning

This is the core of the game. The goal is for each target to **expire exactly on the beat** — so the visual shrink and the musical beat are in sync.

**How it's calculated:**

```
beat_interval     = 60.0 / BPM
                  = 60.0 / 105  ≈  0.571 seconds per beat

beat_times        = FIRST_BEAT_OFFSET + (N * beat_interval)
                  = 1.2, 1.771, 2.343, 2.914, ...

spawn_times       = beat_time - TARGET_LIFETIME
                  = 0.0, 0.571, 1.143, 1.714, ...

spawn_clock       = song_time - (FIRST_BEAT_OFFSET - TARGET_LIFETIME)
```

When `spawn_clock` crosses a new beat index, a target is spawned. Each target is assigned an `expire_time` locked to its specific beat:

```python
expire_time = FIRST_BEAT_OFFSET + current_beat * beat_interval
```

This means no matter when the target spawns (even if there's a tiny delay), it will always expire at the mathematically correct beat time — not N seconds after it appeared.

---

### 3. Target Lifecycle

Each target goes through these stages:

```
[SPAWNED]
    │
    ▼
[VISIBLE]  ← filled magenta circle + shrinking white ring
    │
    ├── finger touches it → [HIT]   → score +10, burst effect
    │
    └── time_left <= 0   → [MISSED] → score -10, red outline flash
```

The shrinking ring uses linear interpolation:

```python
age_frac    = 1.0 - (time_left / TARGET_LIFETIME)   # 0.0 → 1.0
ring_radius = int(TARGET_RADIUS * (1.0 - age_frac)) # shrinks to 0
```

When `age_frac` reaches `1.0`, `ring_radius` is `0` — exactly on the beat.

---

### 4. Hit Detection

Each frame, for every active target, the game checks the Euclidean distance between every detected fingertip and the target centre:

```python
math.dist(finger, (target["x"], target["y"])) < TARGET_RADIUS + HIT_PADDING
```

`HIT_PADDING` (default 15px) adds a small leniency zone outside the visible circle so hits don't feel pixel-perfect strict. The first fingertip that satisfies this condition registers the hit and removes the target immediately.

---

### 5. Scoring System

| Event | Score Change |
|---|---|
| Hit a target | **+10** |
| Miss a target (expires unhit) | **-10** |
| Screen full / beat skipped | No penalty |

**Accuracy** is calculated only from targets that actually appeared on screen:

```python
total_shown = total_hit + total_missed
accuracy    = (total_hit / total_shown) * 100
```

Beats that were silently skipped (screen too full, no safe spawn position) are **not** counted as misses. Only targets the player could actually see are judged.

---

## 🔄 Game States

The game runs as a state machine with 5 states:

```
duration_select
      │
      ▼ (finger touches button)
start_screen
      │
      ▼ (finger touches START)
countdown  →  3... 2... 1...
      │
      ▼ (countdown ends, music starts)
playing
      │
      ▼ (time runs out or song ends)
game_over
```

| State | What happens |
|---|---|
| `duration_select` | Three buttons: 30 SEC / 60 SEC / FULL SONG. Touch one with your finger to select. |
| `start_screen` | Shows a START button. Touch it to begin the countdown. |
| `countdown` | Displays 3, 2, 1 over the camera feed. Music starts immediately after. |
| `playing` | Active gameplay. Targets spawn on the beat. Timer shown top-right. |
| `game_over` | Darkened overlay showing final score, shown count, hit, missed, accuracy. |

---

## 📁 Project Structure

```
beat-tapper-game/
│
├── main.py            # Main game script (all logic in one file)
├── song.mp3           # Background music track
├── miss.mp3           # Sound effect for missed targets
├── requirements.txt   # Python dependencies
└── README.md          # This file
```

All game logic lives in `main.py`. There are no submodules, no classes, no separate files — it's intentionally kept as a single script for simplicity.

---

## 📦 Requirements

**Python version:** 3.10.x recommended (3.11 also works)

> ⚠️ Python 3.12+ may have issues with some MediaPipe builds. Python 3.14 (default on Arch Linux) will cause pygame to compile from source which takes 10+ minutes. Use 3.10 or 3.11 for best experience.

**Dependencies:**

```
opencv-python
mediapipe==0.10.9
pygame
numpy
```

**System requirements:**
- Webcam (built-in or USB)
- Reasonably well-lit room (MediaPipe hand tracking works best with good lighting)
- Speakers or headphones

---

## 💻 Installation

### Windows

```bash
# 1. Clone the repo
git clone https://github.com/saucy-dev/beat-tapper-game.git
cd beat-tapper-game

# 2. Create a virtual environment
python -m venv venv
venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt
```

---

### Linux (Arch)

Arch ships Python 3.14 by default which causes pygame to compile from source (slow). Use pyenv to get Python 3.10 instead:

```bash
# 1. Install pyenv and build dependencies
sudo pacman -S pyenv base-devel cmake protobuf

# 2. Add pyenv to fish shell config
echo 'set -x PYENV_ROOT $HOME/.pyenv' >> ~/.config/fish/config.fish
echo 'set -x PATH $PYENV_ROOT/bin $PATH' >> ~/.config/fish/config.fish
echo 'pyenv init - | source' >> ~/.config/fish/config.fish
source ~/.config/fish/config.fish

# If using bash instead of fish:
# echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.bashrc
# echo 'export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.bashrc
# echo 'eval "$(pyenv init -)"' >> ~/.bashrc
# source ~/.bashrc

# 3. Install Python 3.10
pyenv install 3.10.14

# 4. Clone the repo and set local Python version
git clone https://github.com/saucy-dev/beat-tapper-game.git
cd beat-tapper-game
pyenv local 3.10.14

# 5. Create virtual environment and install
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

### macOS

```bash
# 1. Install pyenv via Homebrew (recommended)
brew install pyenv
echo 'eval "$(pyenv init -)"' >> ~/.zshrc
source ~/.zshrc

# 2. Install Python 3.10
pyenv install 3.10.14

# 3. Clone and setup
git clone https://github.com/saucy-dev/beat-tapper-game.git
cd beat-tapper-game
pyenv local 3.10.14
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

> **macOS camera permission:** On first run, macOS will ask for camera access. Click Allow, then rerun the script.

---

## ▶️ Running the Game

```bash
# Make sure your venv is active
source venv/bin/activate       # Linux/macOS
# or
venv\Scripts\activate          # Windows

# Run
python main.py
```

Press **ESC** at any time to quit.

---

## ⚙️ Configuration & Tuning

All tunable values are at the top of `main.py` under the `# CONFIG` section.

### BPM and Beat Offset

```python
BPM = 105
FIRST_BEAT_OFFSET = 1.2
```

- **`BPM`** — beats per minute of your song. Find this with a tap-tempo tool or DAW.
- **`FIRST_BEAT_OFFSET`** — how many seconds into the audio the first beat lands.

**How to tune `FIRST_BEAT_OFFSET`:**

Play the game and watch when targets expire relative to the beat:

| What you observe | What to do |
|---|---|
| Target expires **before** the beat | **Increase** `FIRST_BEAT_OFFSET` |
| Target expires **after** the beat | **Decrease** `FIRST_BEAT_OFFSET` |
| Target expires exactly on the beat | ✅ Perfect, leave it |

Adjust in small increments of `0.05` until it feels right.

---

### Target Lifetime

```python
TARGET_LIFETIME = 1.2
```

This controls two things simultaneously:
1. **How long the target is visible** on screen
2. **How early before the beat** it spawns

Increasing this gives players more reaction time but makes the screen feel more cluttered. Decreasing it makes the game feel snappier but harder.

At 105 BPM, `beat_interval ≈ 0.571s`. If `TARGET_LIFETIME > beat_interval`, multiple targets can be on screen simultaneously, which is intentional.

---

### Safe Distance Fallbacks

```python
SAFE_DISTANCE_FALLBACKS = [300, 200, 120, 60]
```

When a new target is about to spawn, the game tries to find a position that is at least this many pixels away from:
- Your fingertips
- The previously spawned target
- All currently active targets

It tries each distance in order. If even 60px spacing fails (very crowded screen), it force-spawns at a random position anyway so no beat is ever silently dropped.

Lower these values if you notice many beats being skipped. Raise them for a cleaner visual layout.

---

### Swapping the Song

1. Replace `song.mp3` with your own audio file (keep the filename, or update `MUSIC_FILE` at the top of the script)
2. Find the BPM of your new song (use [tunebat.com](https://tunebat.com) or a DAW)
3. Update `BPM` in the config
4. Run the game and tune `FIRST_BEAT_OFFSET` until targets expire on the beat

Any `.mp3` file works. You can also use `.ogg` or `.wav` — just change the `MUSIC_FILE` extension.

---

## 🎯 Controls

| Action | How |
|---|---|
| Navigate menus | Move your index finger over a button |
| Hit a target | Move your index finger onto the circle |
| Use both hands | Both index fingers are tracked simultaneously |
| Quit | Press **ESC** |

There are no keyboard controls during gameplay — everything is hand-based.

---

## 🛠 Troubleshooting

### Targets not spawning on beat

**Symptom:** Targets appear randomly, not in sync with the music.

**Fix:** Your `FIRST_BEAT_OFFSET` is wrong for your song. See [BPM and Beat Offset](#bpm-and-beat-offset) above. The most common cause is not measuring where the first beat actually lands in the audio file.

---

### MediaPipe solutions error

**Symptom:**
```
AttributeError: module 'mediapipe' has no attribute 'solutions'
```

**Cause:** You have MediaPipe 0.10.x or newer which changed its API.

**Fix:**
```bash
pip install mediapipe==0.10.9
```

---

### Pygame compiling from source

**Symptom:** `pip install` hangs at `Building wheels for collected packages: pygame` for 5-10 minutes.

**Cause:** Your Python version (likely 3.12+) doesn't have a prebuilt pygame wheel, so pip compiles it from C source.

**Fix:** Use Python 3.10 or 3.11 via pyenv — these have prebuilt wheels and install in seconds. See [Installation → Linux (Arch)](#linux-arch).

---

### Webcam not detected

**Symptom:** Black screen or `cap.read()` returns `False`.

**Fix:** The game defaults to `cv2.VideoCapture(0)` which is your first webcam. If you have multiple cameras, try changing `0` to `1` or `2`:

```python
cap = cv2.VideoCapture(1)   # try 1, 2, etc.
```

On Linux, also check:
```bash
ls /dev/video*   # should show /dev/video0
```

---

### Extra misses being counted

**Symptom:** The missed counter seems 1 or 2 higher than expected.

**Cause (fixed in latest version):** An earlier version of the code double-counted targets that were still on screen when the timer ran out — once in the timeout block and once in the natural expiry loop.

**Fix:** Make sure your `main.py` does **not** have this pattern in the duration timeout block:

```python
# BAD — causes double counting
for t in targets:
    total_missed += 1
    score -= 10
targets.clear()

# CORRECT — just clear, no penalty
targets.clear()
```

---

### Hand not detected

**Symptom:** No cyan dot appears on your fingertip.

**Fixes:**
- Improve lighting — MediaPipe struggles in dark rooms
- Make sure your hand is fully in frame
- Try moving your hand closer to the camera
- Avoid busy/cluttered backgrounds if possible

---

## 📦 Building an Executable

To create a double-clickable `.exe` (Windows) or binary that runs without Python installed:

**Step 1 — Add resource path helper at the top of `main.py`:**

```python
import os, sys

def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

MUSIC_FILE = resource_path("song.mp3")
MISS_SOUND = resource_path("miss.mp3")
```

Remove the original `MUSIC_FILE` and `MISS_SOUND` lines from the CONFIG section.

**Step 2 — Install PyInstaller:**

```bash
pip install pyinstaller
```

**Step 3 — Build:**

```bash
# Windows
pyinstaller --onefile --noconsole --add-data "song.mp3;." --add-data "miss.mp3;." main.py

# Linux / macOS
pyinstaller --onefile --noconsole --add-data "song.mp3:." --add-data "miss.mp3:." main.py
```

**Step 4 — Find your executable:**

```
dist/
└── main.exe    ← share this file (Windows)
└── main        ← share this file (Linux/macOS)
```

> ⚠️ The executable only runs on the same OS it was built on. A Windows `.exe` won't run on Linux and vice versa.

---

## ⚠️ Known Limitations

- **OS-specific executables** — PyInstaller builds are platform-locked. You'd need to build separately on Windows, Linux, and macOS.
- **Lighting dependent** — MediaPipe hand tracking degrades significantly in low light or with a cluttered background.
- **Single song** — the game is hardcoded to one song. Swapping requires editing the config manually.
- **No difficulty levels** — BPM and target lifetime are fixed per run. A proper difficulty system would adjust these dynamically.
- **No replay / high score** — scores are not saved between sessions.
- **Beat skip on crowded screen** — if `MAX_TARGETS` is reached, beats are skipped silently. This is intentional (no penalty) but means the game doesn't guarantee every beat spawns a target.

---

## 💡 Future Ideas

- [ ] Song selection screen with automatic BPM detection
- [ ] Difficulty presets (Easy / Medium / Hard) that adjust target size, lifetime, and speed
- [ ] High score leaderboard saved to a local file
- [ ] Combo multiplier — consecutive hits increase score per hit
- [ ] Visual beat pulse on the background in sync with the music
- [ ] Support for two-player mode (one hand each)
- [ ] Better spawn algorithm — grid-based zones instead of random placement
- [ ] Pause / resume functionality
- [ ] Calibration screen to set `FIRST_BEAT_OFFSET` interactively

---

## 🧰 Tech Stack

| Library | Version | Purpose |
|---|---|---|
| Python | 3.10.x | Language |
| opencv-python | 4.x | Camera capture, all rendering |
| mediapipe | 0.10.9 | Real-time hand landmark detection |
| pygame | 2.x | Audio playback, music clock |
| numpy | latest | Frame array manipulation |

---

## 📄 License

This project is open source. Do whatever you want with it — learn from it, build on it, break it, fix it.

If you make something cool inspired by this, I'd love to see it. 🎵

---

<br>

> *"When you love games, music, and programming all at once — sometimes your brain just goes: what if I combined all three?"*
