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
MAX_TARGETS = 6

# Safe distance tries these values in order until a spot is found.
# Starts strict, falls back to more lenient if the screen is crowded.
SAFE_DISTANCE_FALLBACKS = [300, 200, 120, 60]

beat_interval = 60.0 / BPM

# Set True to show why beats are being skipped (useful for tuning)
DEBUG_SKIP = True

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

targets = []
bursts = []
miss_effects = []

score = 0
total_hit = 0
total_missed = 0

last_spawned_beat = -1
last_spawn_position = None

# For debug overlay: reason last beat was skipped
skip_reason = ""
skip_reason_timer = 0  # frames to show it

# -----------------------------
# Helper: Try to find a safe spawn position
# Uses progressively relaxed distances if strict placement fails
# Returns (x, y) or None
# -----------------------------
def find_spawn_position(w, h, fingertips, targets, last_pos):
    margin = 150

    for safe_dist in SAFE_DISTANCE_FALLBACKS:
        for _ in range(60):
            sx = random.randint(margin, w - margin)
            sy = random.randint(margin, h - margin)

            ok = True
            for finger in fingertips:
                if math.dist(finger, (sx, sy)) < safe_dist:
                    ok = False; break

            if ok and last_pos:
                if math.dist((sx, sy), last_pos) < safe_dist:
                    ok = False

            if ok:
                for t in targets:
                    if math.dist((sx, sy), (t["x"], t["y"])) < safe_dist:
                        ok = False; break

            if ok:
                return (sx, sy)

    return None  # no spot found even at minimum distance

# -----------------------------
# Helper: Draw Button
# -----------------------------
def draw_button(frame, text, center, size=(300,100), color=(0,255,0)):
    bw, bh = size
    x1 = center[0] - bw//2
    y1 = center[1] - bh//2
    x2 = x1 + bw
    y2 = y1 + bh
    cv2.rectangle(frame, (x1,y1), (x2,y2), color, -1)
    cv2.putText(frame, text, (x1+30, y1+65),
                cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0,0,0), 3)
    return (x1, y1, x2, y2)

# -----------------------------
# Helper: Draw Timer (top right)
# -----------------------------
def draw_timer(frame, song_time, duration, fw):
    if duration == "full":
        mins = int(song_time) // 60
        secs = int(song_time) % 60
        timer_text = f"{mins}:{secs:02d}"
        label = "TIME"
    else:
        remaining = max(0, duration - song_time)
        mins = int(remaining) // 60
        secs = int(remaining) % 60
        timer_text = f"{mins}:{secs:02d}"
        label = "LEFT"

    box_x = fw - 210
    cv2.rectangle(frame, (box_x - 10, 10), (fw - 10, 90), (0,0,0), -1)
    cv2.rectangle(frame, (box_x - 10, 10), (fw - 10, 90), (255,255,255), 2)
    cv2.putText(frame, label,       (box_x, 38), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (180,180,180), 2)
    cv2.putText(frame, timer_text,  (box_x, 78), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (255,255,0),   3)

    if duration != "full":
        bar_x1 = box_x - 10
        bar_x2 = fw - 10
        bar_y  = 92
        bar_w  = bar_x2 - bar_x1
        progress = min(1.0, song_time / duration)
        cv2.rectangle(frame, (bar_x1, bar_y), (bar_x2, bar_y + 6), (50,50,50), -1)
        cv2.rectangle(frame, (bar_x1, bar_y),
                      (bar_x1 + int(bar_w * progress), bar_y + 6),
                      (0,200,255), -1)

# -----------------------------
# Main Loop
# -----------------------------
while True:
    ret, frame = cap.read()
    if not ret:
        break

    frame = cv2.flip(frame, 1)
    fh, fw, _ = frame.shape

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = hands.process(rgb)

    fingertips = []
    if results.multi_hand_landmarks:
        for landmarks in results.multi_hand_landmarks:
            mp_drawing.draw_landmarks(frame, landmarks, mp_hands.HAND_CONNECTIONS)
            ix = int(landmarks.landmark[8].x * fw)
            iy = int(landmarks.landmark[8].y * fh)
            fingertips.append((ix, iy))
            cv2.circle(frame, (ix, iy), 10, (0,255,255), -1)

    # =============================
    # STATE: DURATION SELECT
    # =============================
    if state == "duration_select":
        b1 = draw_button(frame, "30 SEC",    (fw//2, 250))
        b2 = draw_button(frame, "60 SEC",    (fw//2, 400))
        b3 = draw_button(frame, "FULL SONG", (fw//2, 550))
        for finger in fingertips:
            if b1[0] < finger[0] < b1[2] and b1[1] < finger[1] < b1[3]:
                selected_duration = 30;     state = "start_screen"
            if b2[0] < finger[0] < b2[2] and b2[1] < finger[1] < b2[3]:
                selected_duration = 60;     state = "start_screen"
            if b3[0] < finger[0] < b3[2] and b3[1] < finger[1] < b3[3]:
                selected_duration = "full"; state = "start_screen"

    # =============================
    # STATE: START SCREEN
    # =============================
    elif state == "start_screen":
        start_btn = draw_button(frame, "START", (fw//2, fh//2), (350,120))
        for finger in fingertips:
            if start_btn[0] < finger[0] < start_btn[2] and start_btn[1] < finger[1] < start_btn[3]:
                state = "countdown"
                countdown_start = time.time()

    # =============================
    # STATE: COUNTDOWN
    # =============================
    elif state == "countdown":
        elapsed = time.time() - countdown_start
        if elapsed < 1:   text = "3"
        elif elapsed < 2: text = "2"
        elif elapsed < 3: text = "1"
        else:
            pygame.mixer.music.play()
            last_spawned_beat = -1
            state = "playing"
            continue
        cv2.putText(frame, text, (fw//2 - 50, fh//2),
                    cv2.FONT_HERSHEY_SIMPLEX, 5, (0,0,255), 8)

    # =============================
    # STATE: PLAYING
    # =============================
    elif state == "playing":
        song_time_ms = pygame.mixer.music.get_pos()

        if song_time_ms < 0:
            state = "game_over"
        else:
            song_time = song_time_ms / 1000.0

            draw_timer(frame, song_time, selected_duration, fw)

            if selected_duration != "full" and song_time >= selected_duration:
                # Just clear — no penalty. Targets that naturally expired
                # were already counted as misses in the update loop below.
                # Penalising here too would double-count them.
                targets.clear()
                pygame.mixer.music.stop()
                state = "game_over"

            # ── Beat-accurate spawn clock ──────────────────────
            spawn_clock = song_time - (FIRST_BEAT_OFFSET - TARGET_LIFETIME)

            if spawn_clock >= 0:
                current_beat = int(spawn_clock / beat_interval)

                if current_beat > last_spawned_beat:
                    last_spawned_beat = current_beat

                    if len(targets) >= MAX_TARGETS:
                        # Screen full — skip silently, no penalty
                        if DEBUG_SKIP:
                            skip_reason = f"SKIP: screen full ({len(targets)}/{MAX_TARGETS})"
                            skip_reason_timer = 40
                    else:
                        pos = find_spawn_position(fw, fh, fingertips, targets, last_spawn_position)
                        if pos:
                            expire_time = FIRST_BEAT_OFFSET + current_beat * beat_interval
                            targets.append({
                                "x": pos[0],
                                "y": pos[1],
                                "spawn_time": song_time,
                                "expire_time": expire_time
                            })
                            last_spawn_position = pos
                        else:
                            # Even minimum distance failed — force random spawn
                            sx = random.randint(150, fw - 150)
                            sy = random.randint(150, fh - 150)
                            expire_time = FIRST_BEAT_OFFSET + current_beat * beat_interval
                            targets.append({
                                "x": sx,
                                "y": sy,
                                "spawn_time": song_time,
                                "expire_time": expire_time
                            })
                            last_spawn_position = (sx, sy)
                            if DEBUG_SKIP:
                                skip_reason = "FORCED: no safe spot found"
                                skip_reason_timer = 40

            # ── Update & draw targets ──────────────────────────
            for target in targets[:]:
                time_left = target["expire_time"] - song_time
                age_frac  = 1.0 - (time_left / TARGET_LIFETIME)

                if time_left <= 0:
                    score -= 10
                    total_missed += 1
                    miss_sound.play()
                    miss_effects.append((target["x"], target["y"], 8))
                    targets.remove(target)
                    continue

                cv2.circle(frame, (target["x"], target["y"]),
                           TARGET_RADIUS, (180, 0, 180), -1)

                ring_radius = int(TARGET_RADIUS * (1.0 - age_frac))
                if ring_radius > 0:
                    cv2.circle(frame, (target["x"], target["y"]),
                               ring_radius, (255, 255, 255), 4)

                for finger in fingertips:
                    if math.dist(finger, (target["x"], target["y"])) < TARGET_RADIUS + HIT_PADDING:
                        score += 10
                        total_hit += 1
                        bursts.append((target["x"], target["y"], 8))
                        targets.remove(target)
                        break

        cv2.putText(frame, f"Score: {score}", (30, 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.5, (255,255,255), 3)

        # Debug skip reason
        if DEBUG_SKIP and skip_reason_timer > 0:
            cv2.putText(frame, skip_reason, (30, fh - 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 200, 255), 2)
            skip_reason_timer -= 1

    # =============================
    # DRAW BURSTS
    # =============================
    for b in bursts[:]:
        x, y, life = b
        cv2.circle(frame, (x, y), 40 + (8-life)*10, (0,255,255), 3)
        life -= 1
        bursts.remove(b)
        if life > 0:
            bursts.append((x, y, life))

    # =============================
    # DRAW MISS OUTLINE
    # =============================
    for m in miss_effects[:]:
        x, y, life = m
        cv2.circle(frame, (x, y), TARGET_RADIUS + 20, (0,0,255), 5)
        life -= 1
        miss_effects.remove(m)
        if life > 0:
            miss_effects.append((x, y, life))

    # =============================
    # STATE: GAME OVER
    # =============================
    if state == "game_over":
        overlay = frame.copy()
        cv2.rectangle(overlay, (200,150), (1080,650), (0,0,0), -1)
        frame = cv2.addWeighted(overlay, 0.7, frame, 0.3, 0)

        total_shown = total_hit + total_missed
        accuracy = (total_hit / total_shown * 100) if total_shown > 0 else 0

        cv2.putText(frame, "GAME OVER",                (450,250), cv2.FONT_HERSHEY_SIMPLEX, 2.5, (0,0,255),    6)
        cv2.putText(frame, f"Final Score: {score}",    (420,330), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (255,255,255), 3)
        cv2.putText(frame, f"Shown: {total_shown}",    (420,380), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255,255,255), 2)
        cv2.putText(frame, f"Hit: {total_hit}",         (420,420), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0,255,0),    2)
        cv2.putText(frame, f"Missed: {total_missed}",   (420,460), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0,0,255),    2)
        cv2.putText(frame, f"Accuracy: {accuracy:.1f}%",(420,500), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255,255,0),  2)
        cv2.putText(frame, "Press ESC to Exit",         (450,560), cv2.FONT_HERSHEY_SIMPLEX, 1,   (255,255,255), 2)

    cv2.imshow("Rhythm Game", frame)
    if cv2.waitKey(1) & 0xFF == 27:
        break

cap.release()
cv2.destroyAllWindows()
pygame.mixer.music.stop()