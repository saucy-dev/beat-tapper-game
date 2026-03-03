import cv2
import mediapipe as mp
import pygame
import math
import random
import numpy as np
import time

# -----------------------------
# CONFIG
# -----------------------------
MUSIC_FILE = "song.mp3"
MISS_SOUND = "miss.mp3"

BPM = 105
FIRST_BEAT_OFFSET = 1.2

TARGET_LIFETIME = 1.2
TARGET_RADIUS = 90
HIT_PADDING = 15
SPAWN_SAFE_DISTANCE = 300
MAX_TARGETS = 4

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

cv2.namedWindow("Rhythm Game", cv2.WINDOW_NORMAL)
cv2.resizeWindow("Rhythm Game", 1280, 720)

# -----------------------------
# Game Variables
# -----------------------------
state = "duration_select"

selected_duration = None
game_duration = None
game_start_time = None

targets = []
bursts = []
miss_effects = []

score = 0
total_spawned = 0
total_hit = 0
total_missed = 0

last_spawned_beat = -1
last_spawn_position = None

# -----------------------------
# Helper: Draw Button
# -----------------------------
def draw_button(frame, text, center, size=(300,100), color=(0,255,0)):
    w,h = size
    x1 = center[0] - w//2
    y1 = center[1] - h//2
    x2 = x1 + w
    y2 = y1 + h

    cv2.rectangle(frame, (x1,y1), (x2,y2), color, -1)
    cv2.putText(frame, text,
                (x1+30, y1+65),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.5,(0,0,0),3)

    return (x1,y1,x2,y2)

# -----------------------------
# Main Loop
# -----------------------------
while True:
    ret, frame = cap.read()
    if not ret:
        break

    frame = cv2.flip(frame, 1)
    h, w, _ = frame.shape

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = hands.process(rgb)

    fingertips = []

    if results.multi_hand_landmarks:
        for landmarks in results.multi_hand_landmarks:
            mp_drawing.draw_landmarks(
                frame, landmarks, mp_hands.HAND_CONNECTIONS)

            ix = int(landmarks.landmark[8].x * w)
            iy = int(landmarks.landmark[8].y * h)
            fingertips.append((ix, iy))
            cv2.circle(frame, (ix, iy), 10, (0,255,255), -1)

    # =============================
    # STATE: DURATION SELECT
    # =============================
    if state == "duration_select":

        b1 = draw_button(frame, "30 SEC", (w//2, 250))
        b2 = draw_button(frame, "60 SEC", (w//2, 400))
        b3 = draw_button(frame, "FULL SONG", (w//2, 550))

        for finger in fingertips:
            if b1[0] < finger[0] < b1[2] and b1[1] < finger[1] < b1[3]:
                selected_duration = 30
                state = "start_screen"
            if b2[0] < finger[0] < b2[2] and b2[1] < finger[1] < b2[3]:
                selected_duration = 60
                state = "start_screen"
            if b3[0] < finger[0] < b3[2] and b3[1] < finger[1] < b3[3]:
                selected_duration = "full"
                state = "start_screen"

    # =============================
    # STATE: START SCREEN
    # =============================
    elif state == "start_screen":

        start_btn = draw_button(frame, "START", (w//2, h//2), (350,120))

        for finger in fingertips:
            if start_btn[0] < finger[0] < start_btn[2] and start_btn[1] < finger[1] < start_btn[3]:
                state = "countdown"
                countdown_start = time.time()

    # =============================
    # STATE: COUNTDOWN
    # =============================
    elif state == "countdown":

        elapsed = time.time() - countdown_start

        if elapsed < 1:
            text = "3"
        elif elapsed < 2:
            text = "2"
        elif elapsed < 3:
            text = "1"
        else:
            pygame.mixer.music.play()
            game_start_time = time.time()
            state = "playing"
            continue

        cv2.putText(frame, text,
                    (w//2 - 50, h//2),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    5,(0,0,255),8)

    # =============================
    # STATE: PLAYING
    # =============================
    elif state == "playing":

        song_time_ms = pygame.mixer.music.get_pos()
        if song_time_ms < 0:
            state = "game_over"
        else:
            song_time = song_time_ms / 1000.0
            adjusted_time = song_time - FIRST_BEAT_OFFSET

            # Stop if time limit reached
            if selected_duration != "full":
                if time.time() - game_start_time > selected_duration:
                    pygame.mixer.music.stop()
                    state = "game_over"

            # Spawn logic
            if adjusted_time >= 0:
                current_beat = int(adjusted_time / beat_interval)

                if current_beat > last_spawned_beat and len(targets) < MAX_TARGETS:
                    last_spawned_beat = current_beat
                    total_spawned += 1

                    margin = 200

                    for _ in range(40):
                        spawn_x = random.randint(margin, w - margin)
                        spawn_y = random.randint(margin, h - margin)

                        safe = True

                        # Away from fingertips
                        for finger in fingertips:
                            if math.dist(finger,(spawn_x,spawn_y)) < SPAWN_SAFE_DISTANCE:
                                safe = False

                        # Away from previous target
                        if last_spawn_position:
                            if math.dist((spawn_x,spawn_y), last_spawn_position) < SPAWN_SAFE_DISTANCE:
                                safe = False

                        # Away from all active targets
                        for existing in targets:
                            if math.dist((spawn_x,spawn_y),
                                         (existing["x"],existing["y"])) < SPAWN_SAFE_DISTANCE:
                                safe = False

                        if safe:
                            targets.append({
                                "x":spawn_x,
                                "y":spawn_y,
                                "spawn_time":song_time
                            })
                            last_spawn_position = (spawn_x,spawn_y)
                            break

            # Update targets
            for target in targets[:]:

                age = song_time - target["spawn_time"]

                if age > TARGET_LIFETIME:
                    score -= 10
                    total_missed += 1
                    miss_sound.play()
                    targets.remove(target)
                    continue

                cv2.circle(frame,
                           (target["x"],target["y"]),
                           TARGET_RADIUS,
                           (255,0,255),-1)

                for finger in fingertips:
                    if math.dist(finger,
                                 (target["x"],target["y"])) < TARGET_RADIUS + HIT_PADDING:
                        score += 10
                        total_hit += 1
                        targets.remove(target)
                        break

        cv2.putText(frame,
                    f"Score: {score}",
                    (30,50),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1.5,(255,255,255),3)

    # =============================
    # STATE: GAME OVER
    # =============================
    elif state == "game_over":

        overlay = frame.copy()
        cv2.rectangle(overlay,(200,150),(1080,600),(0,0,0),-1)
        frame = cv2.addWeighted(overlay,0.7,frame,0.3,0)

        cv2.putText(frame,"GAME OVER",
                    (450,250),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    2.5,(0,0,255),6)

        cv2.putText(frame,f"Final Score: {score}",
                    (420,330),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1.5,(255,255,255),3)

        cv2.putText(frame,f"Spawned: {total_spawned}",
                    (420,380),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1.2,(255,255,255),2)

        cv2.putText(frame,f"Hit: {total_hit}",
                    (420,420),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1.2,(0,255,0),2)

        cv2.putText(frame,f"Missed: {total_missed}",
                    (420,460),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1.2,(0,0,255),2)

        cv2.putText(frame,"Press ESC to Exit",
                    (450,520),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1,(255,255,255),2)

    cv2.imshow("Rhythm Game", frame)

    if cv2.waitKey(1) & 0xFF == 27:
        break

cap.release()
cv2.destroyAllWindows()
pygame.mixer.music.stop()