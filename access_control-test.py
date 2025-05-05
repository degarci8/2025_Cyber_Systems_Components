#!/usr/bin/env python3
"""
access_control.py

Edge device access control using OpenCV LBPH recognizer:
- Prompt for 4-digit PIN via keypad (or console fallback)
- Match PIN to user data
- Perform face detection/matching on stored vs. live image
- Grant/deny access and log attempts
"""
import os
import json
import time
import numpy as np
from datetime import datetime
import cv2
from google.cloud import firestore
import RPi.GPIO as GPIO
try:
    from pad4pi import rpi_gpio
except ImportError:
    rpi_gpio = None

# Configuration
PROJECT_DIR = "/home/raspberrypi/Projects"
DATA_DIR = os.path.join(PROJECT_DIR, "data")
IMAGE_DIR = os.path.join(DATA_DIR, "images")
USERS_FILE = os.path.join(DATA_DIR, "authorized_users.json")
LOG_DIR = os.path.join(PROJECT_DIR, "logs")
LOG_FILE = os.path.join(LOG_DIR, "access.log")

KEYPAD_ROWS = [17, 27, 22, 5]
KEYPAD_COLS = [23, 24, 25, 16]
KEYPAD_KEYS = [
    ["1","2","3","A"],
    ["4","5","6","B"],
    ["7","8","9","C"],
    ["*","0","#","D"]
]

FACE_CONFIDENCE_THRESHOLD = 60.0
face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
)
LOG_COLLECTION = "access_logs"

# Setup
os.makedirs(LOG_DIR, exist_ok=True)

# Firestore client
db = firestore.Client()

# GPIO setup
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
for pin in KEYPAD_ROWS:
    GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
for pin in KEYPAD_COLS:
    GPIO.setup(pin, GPIO.OUT)
    GPIO.output(pin, GPIO.LOW)

# Keypad initialization with fallback
use_keypad = False
keypad = None
if rpi_gpio:
    try:
        factory = rpi_gpio.KeypadFactory()
        keypad = factory.create_keypad(
            keypad=KEYPAD_KEYS,
            row_pins=KEYPAD_ROWS,
            col_pins=KEYPAD_COLS
        )
        use_keypad = True
    except Exception as e:
        print(f"Warning: Keypad init failed ({e}); falling back to console input.")
else:
    print("Warning: pad4pi not installed; falling back to console PIN entry.")

def get_pin_input(length=4):
    if use_keypad and keypad:
        pin = ""
        def handler(key):
            nonlocal pin
            if key not in ['A','B','C','D','*','#']:
                print(key, end='', flush=True)
                pin += key
                if len(pin) >= length:
                    keypad.unregisterKeyPressHandler(handler)
        print("Enter PIN:", end=' ', flush=True)
        keypad.registerKeyPressHandler(handler)
        while len(pin) < length:
            time.sleep(0.1)
        print()
        return pin
    else:
        # Console fallback
        pin = None
        while not pin or len(pin) != length or not pin.isdigit():
            pin = input(f"Enter {length}-digit PIN: ")
        return pin

def detect_face_gray(image):
    faces = face_cascade.detectMultiScale(image, 1.1, 5)
    if len(faces) == 0:
        return None
    x, y, w, h = faces[0]
    return image[y:y+h, x:x+w]

def capture_face_gray():
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Warning: Cannot open camera")
        return None
    ret, frame = cap.read()
    cap.release()
    if not ret:
        print("Warning: Failed to capture image")
        return None
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return detect_face_gray(gray)

def log_access(user_id, pin, success):
    ts = datetime.utcnow().isoformat()
    entry = {"timestamp": ts, "pin_entered": pin, "user_id": user_id, "success": success}
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")
    try:
        db.collection(LOG_COLLECTION).add(entry)
    except Exception:
        print("Warning: Failed to log to Firestore")

def main():
    with open(USERS_FILE) as f:
        users = {u['pin']: u for u in json.load(f)}

    pin = get_pin_input()
    user = users.get(pin)
    if not user:
        print("Access denied: PIN not recognized")
        log_access(None, pin, False)
        return

    print(f"User {user['name']} ({user['id']}) PIN valid")
    # Load stored face
    img = cv2.imread(user['local_image_path'], cv2.IMREAD_GRAYSCALE)
    stored_face = None
    if img is not None:
        stored_face = detect_face_gray(img)
    if stored_face is None:
        print("Face verification failed: stored image error")
        log_access(user['id'], pin, False)
        return

    # Capture live face
    live_face = capture_face_gray()
    if live_face is None:
        print("Face verification failed: live capture error")
        log_access(user['id'], pin, False)
        return

    # Perform LBPH matching
    try:
        recognizer = cv2.face.LBPHFaceRecognizer_create()
        recognizer.train([stored_face], np.array([0]))
        _, conf = recognizer.predict(live_face)
    except Exception as e:
        print(f"Face verification error: {e}")
        log_access(user['id'], pin, False)
        return

    if conf <= FACE_CONFIDENCE_THRESHOLD:
        print("Access granted")
        log_access(user['id'], pin, True)
    else:
        print(f"Access denied: mismatch (conf={conf:.2f})")
        log_access(user['id'], pin, False)

if __name__ == "__main__":
    main()
