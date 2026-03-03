# 🎵 Hand Gesture Rhythm Game (OpenCV + MediaPipe)

A real-time rhythm game built using OpenCV and MediaPipe where players hit targets using hand gestures synchronized with music.

Supports two gameplay modes:
- 👆 Tap Mode (Index finger touch)
- 👊 Punch Mode (Forward hand motion)

---

## 🚀 Features

- Real-time hand tracking using MediaPipe
- Beat-synchronized target spawning
- Adjustable BPM support
- First-beat offset calibration
- Tap and Punch gesture modes
- Non-overlapping smart spawn system
- Burst animation effects
- Miss sound feedback
- Optimized for performance

---

## 🧠 Tech Stack

- Python
- OpenCV
- MediaPipe
- Pygame (audio engine)
- NumPy

---

## 🎮 Gameplay

1. Launch the game
2. Select mode:
   - Press **T** for Tap
   - Press **P** for Punch
3. Hit targets on beat
4. Score increases for successful hits

---

## 🛠 Installation

Clone repository:

```bash
git clone https://github.com/saucy-dev/beat-tapper-game.git
cd beat-tapper-game
pip install -r requirements.txt
python main.py
