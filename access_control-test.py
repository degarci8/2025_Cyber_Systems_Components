#!/usr/bin/env python3
"""
access_control.py

Edge device access control:
- Prompt user for 4-digit PIN via keypad
- Look up PIN in local authorized_users.json
- If user found, load stored face image and compare to live capture
- Grant or deny access (servo unlock stub)
- Log access attempt to local file and to Firestore
"""
import os
import json
import time
from datetime import datetime

import cv2
import face_recognition
from pad4pi import rpi_gpio
from google.cloud import firestore

#  CONFIGURATION 
PROJECT_DIR = "/home/raspberrypi/Projects"
DATA_DIR    = os.path.join(PROJECT_DIR, "data")
IMAGE_DIR   = os.path.join(DATA_DIR, "images")
USERS_FILE  = os.path.join(DATA_DIR, "authorized_users.json")
LOG_DIR     = os.path.join(PROJECT_DIR, "logs")
LOG_FILE    = os.path.join(LOG_DIR, "access.log")

# Keypad pins (adjust to your wiring)
KEYPAD_ROWS   = [17, 27, 22, 5]
KEYPAD_COLS   = [23, 24, 25, 16]
KEYPAD_KEYS = [
    ["1", "2", "3", "A"],
    ["4", "5", "6", "B"],
    ["7", "8", "9", "C"],
    ["*", "0", "#", "D"]
]

# Face match tolerance (lower = stricter)
MATCH_TOLERANCE = 0.6

# Firestore collection for logging
LOG_COLLECTION = "access_logs"

#  SETUP 
os.makedirs(LOG_DIR, exist_ok=True)

# Initialize Firestore client for logging
db = firestore.Client()

# Setup keypad
factory = rpi_gpio.KeypadFactory()
keypad = factory.create_keypad(keypad=KEYPAD_KEYS, row_pins=KEYPAD_ROWS, col_pins=KEYPAD_COLS)

#  FUNCTIONS 

def get_pin_input(length=4):
    """Read a fixed-length PIN from the keypad."""
    pin = ""

    def key_handler(key):
        nonlocal pin
        if key in ["A", "B", "C", "D", "*", "#"]:
            return
        print(key, end="", flush=True)
        pin += key
        if len(pin) >= length:
            keypad.unregisterKeyPressHandler(key_handler)

    print("Enter PIN:", end=" ", flush=True)
    keypad.registerKeyPressHandler(key_handler)

    # Wait until PIN is complete
    while len(pin) < length:
        time.sleep(0.1)
    print()
    return pin


def capture_face_image():
    """Capture a single frame from the Pi camera via OpenCV and return RGB image."""
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        raise RuntimeError("Cannot open camera")
    ret, frame = cap.read()
    cap.release()
    if not ret:
        raise RuntimeError("Failed to capture image")
    return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)


def log_access(user_id, pin, success):
    """Log access locally and to Firestore."""
    timestamp = datetime.utcnow().isoformat()
    entry = {
        "timestamp": timestamp,
        "pin_entered": pin,
        "user_id": user_id,
        "success": success
    }
    # Local log
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")
    # Firestore log
    db.collection(LOG_COLLECTION).add(entry)


def unlock_door(duration=5):
    """Stub: activate servo to unlock then relock after duration seconds."""
    print(f"[servo] Unlocking door for {duration}s...")
    # TODO: implement GPIO PWM for servo here
    time.sleep(duration)
    print("[servo] Relocking door")

#  MAIN 

def main():
    # Load authorized users
    with open(USERS_FILE) as f:
        users = {u['pin']: u for u in json.load(f)}

    pin = get_pin_input()
    user = users.get(pin)
    if not user:
        print("Access denied: PIN not recognized")
        log_access(None, pin, False)
        return

    print(f"PIN valid for user {user['name']} (ID: {user['id']})")

    try:
        known_image = face_recognition.load_image_file(user['local_image_path'])
        known_encoding = face_recognition.face_encodings(known_image)[0]

        live_image = capture_face_image()
        live_encodings = face_recognition.face_encodings(live_image)
        if not live_encodings:
            raise ValueError("No face detected")

        match = face_recognition.compare_faces(
            [known_encoding], live_encodings[0], tolerance=MATCH_TOLERANCE
        )[0]
    except Exception as e:
        print(f"Face verification failed: {e}")
        log_access(user['id'], pin, False)
        return

    if match:
        print("Access granted")
        log_access(user['id'], pin, True)
        unlock_door()
    else:
        print("Access denied: face mismatch")
        log_access(user['id'], pin, False)


if __name__ == "__main__":
    main()