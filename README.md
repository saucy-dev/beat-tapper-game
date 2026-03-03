# 🎵 Hand Gesture Rhythm Game (OpenCV + MediaPipe)

A real-time rhythm game built using OpenCV and MediaPipe where players hit beat-synced targets using hand gestures.

Currently supports:

👆 Tap Mode (Index Finger)

---

## 🎮 How It Works

1. Launch the game
2. Tap the **START** button on screen
3. 3-2-1 countdown begins
4. Music starts
5. Targets spawn on beat
6. Tap targets with index finger to score

---

## ⚙ Features

- Real-time hand tracking
- Beat-synchronized spawning
- Start button with CV interaction
- Countdown before gameplay
- Red penalty effect on miss
- Smart spawn (no overlapping)
- Optimized performance
- Score tracking

---

## 🛠 Tech Stack

- Python
- OpenCV
- MediaPipe
- Pygame
- NumPy

---

## 🚀 Installation

```bash
git clone https://github.com/saucy-dev/beat-tapper-game.git
cd beat-tapper-game
pip install -r requirements.txt
python main.py