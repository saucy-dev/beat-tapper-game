import cv2
import mediapipe as mp
import pygame
import math
import random
import numpy as np

# -----------------------------
# CONFIG
# -----------------------------
MUSIC_FILE = "song.mp3"
MISS_SOUND = "miss.mp3"

BPM = 72
FIRST_BEAT_OFFSET = 1.2

TARGET_LIFETIME = 1.2
TARGET_RADIUS = 90
HIT_PADDING = 15
MIN_SPAWN_DISTANCE = 250
MAX_TARGETS = 4

PUNCH_Z_THRESHOLD = 0.18
PUNCH_Y_THRESHOLD = 25
PUNCH_COOLDOWN = 8

beat_interval = 60 / BPM

# -----------------------------
# Setup
# -----------------------------
mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils

hands = mp_hands.Hands(max_num_hands=2)

cap = cv2.VideoCapture(0)
cap.set(3, 1280)
cap.set(4, 720)

pygame.mixer.init()
pygame.mixer.music.load(MUSIC_FILE)
miss_sound = pygame.mixer.Sound(MISS_SOUND)

targets = []
bursts = []
miss_effects = []

score = 0
mode = None  # Auto detect

last_spawned_beat = -1
prev_wrist_data = {}
punch_cooldown = {}

pygame.mixer.music.play()

cv2.namedWindow("Rhythm Game", cv2.WINDOW_NORMAL)
cv2.resizeWindow("Rhythm Game", 1280, 720)

# -----------------------------
# Main Loop
# -----------------------------
while True:
    ret, frame = cap.read()
    if not ret:
        break

    frame = cv2.flip(frame, 1)
    h, w, _ = frame.shape

    song_time_ms = pygame.mixer.music.get_pos()
    if song_time_ms < 0:
        break

    song_time = song_time_ms / 1000.0
    adjusted_time = song_time - FIRST_BEAT_OFFSET

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = hands.process(rgb)

    fingertips = []
    punch_positions = []

    if results.multi_hand_landmarks:
        for idx, landmarks in enumerate(results.multi_hand_landmarks):

            mp_drawing.draw_landmarks(frame, landmarks,
                                      mp_hands.HAND_CONNECTIONS)

            # Index fingertip
            ix = int(landmarks.landmark[8].x * w)
            iy = int(landmarks.landmark[8].y * h)
            fingertips.append((ix, iy))

            # Wrist data
            wx = int(landmarks.landmark[0].x * w)
            wy = int(landmarks.landmark[0].y * h)
            wz = landmarks.landmark[0].z

            if idx not in punch_cooldown:
                punch_cooldown[idx] = 0

            if idx in prev_wrist_data:

                prev_z, prev_y = prev_wrist_data[idx]
                velocity_z = prev_z - wz
                velocity_y = prev_y - wy

                if (velocity_z > PUNCH_Z_THRESHOLD and
                    abs(velocity_y) > PUNCH_Y_THRESHOLD and
                    punch_cooldown[idx] == 0):

                    punch_positions.append((wx, wy))
                    punch_cooldown[idx] = PUNCH_COOLDOWN

            prev_wrist_data[idx] = (wz, wy)

            if punch_cooldown[idx] > 0:
                punch_cooldown[idx] -= 1

    # -----------------------------
    # Beat Spawn
    # -----------------------------
    if adjusted_time >= 0:
        current_beat = int(adjusted_time / beat_interval)

        if current_beat > last_spawned_beat and len(targets) < MAX_TARGETS:
            last_spawned_beat = current_beat

            margin = 200

            for _ in range(25):
                spawn_x = random.randint(margin, w - margin)
                spawn_y = random.randint(margin, h - margin)

                safe = True

                for finger in fingertips:
                    if math.dist(finger, (spawn_x, spawn_y)) < MIN_SPAWN_DISTANCE:
                        safe = False

                for existing in targets:
                    if math.dist((spawn_x, spawn_y),
                                 (existing["x"], existing["y"])) < 2*TARGET_RADIUS:
                        safe = False

                if safe:
                    targets.append({
                        "x": spawn_x,
                        "y": spawn_y,
                        "spawn_time": song_time
                    })
                    break

    # -----------------------------
    # Update Targets
    # -----------------------------
    for target in targets[:]:

        age = song_time - target["spawn_time"]

        if age > TARGET_LIFETIME:
            score -= 10
            miss_sound.play()
            miss_effects.append((target["x"], target["y"], 6))
            targets.remove(target)
            continue

        cv2.circle(frame,
                   (target["x"], target["y"]),
                   TARGET_RADIUS,
                   (255,0,255), -1)

        hit = False

        # Tap detection
        for finger in fingertips:
            if math.dist(finger,
                         (target["x"], target["y"])) < TARGET_RADIUS + HIT_PADDING:
                hit = True
                if mode is None:
                    mode = "tap"
                break

        # Punch detection
        for punch in punch_positions:
            if math.dist(punch,
                         (target["x"], target["y"])) < TARGET_RADIUS:
                hit = True
                if mode is None:
                    mode = "punch"
                break

        if hit:
            score += 10
            bursts.append((target["x"], target["y"], 8))
            targets.remove(target)

    # -----------------------------
    # Miss Red Outline Effect
    # -----------------------------
    for m in miss_effects[:]:
        x,y,life = m
        cv2.circle(frame, (x,y),
                   TARGET_RADIUS+20,
                   (0,0,255), 5)
        life -= 1
        miss_effects.remove(m)
        if life > 0:
            miss_effects.append((x,y,life))

    # -----------------------------
    # Burst
    # -----------------------------
    for b in bursts[:]:
        x,y,life = b
        cv2.circle(frame, (x,y),
                   40 + (8-life)*10,
                   (0,255,255), 3)
        life -= 1
        bursts.remove(b)
        if life > 0:
            bursts.append((x,y,life))

    cv2.putText(frame,
                f"Score: {score}",
                (30,50),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.5,(255,255,255),3)

    if mode:
        cv2.putText(frame,
                    f"Mode: {mode.upper()}",
                    (30,90),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1,(255,255,255),2)

    cv2.imshow("Rhythm Game", frame)

    if cv2.waitKey(1) & 0xFF == 27:
        break

cap.release()
cv2.destroyAllWindows()
pygame.mixer.music.stop()