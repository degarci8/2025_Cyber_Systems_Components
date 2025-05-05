#!/usr/bin/env python3
"""
access_control.py

Edge device access control using OpenCV LBPH recognizer:
- Prompt user for 4-digit PIN via keypad
- Look up PIN in local authorized_users.json
- If user found, detect and match face from live capture to stored image
- Grant or deny access
- Log access attempt to local file and to Firestore
"""
import os
import json
import time
import numpy as np
from datetime import datetime
import cv2
from pad4pi import rpi_gpio
from google.cloud import firestore

#  CONFIGURATION 
PROJECT_DIR   = "/home/raspberrypi/Projects"
DATA_DIR      = os.path.join(PROJECT_DIR, "data")
IMAGE_DIR     = os.path.join(DATA_DIR, "images")
USERS_FILE    = os.path.join(DATA_DIR, "authorized_users.json")
LOG_DIR       = os.path.join(PROJECT_DIR, "logs")
LOG_FILE      = os.path.join(LOG_DIR, "access.log")

# Updated keypad pins
KEYPAD_ROWS = [17, 27, 22, 5]
KEYPAD_COLS = [23, 24, 25, 16]
KEYPAD_KEYS = [
    ["1", "2", "3", "A"],
    ["4", "5", "6", "B"],
    ["7", "8", "9", "C"],
    ["*", "0", "#", "D"]
]

# LBPH face recognizer parameters
FACE_CONFIDENCE_THRESHOLD = 60.0  # lower is stricter
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

# Firestore collection for logging
LOG_COLLECTION = "access_logs"

#  SETUP 
os.makedirs(LOG_DIR, exist_ok=True)

# Initialize Firestore client for logging
db = firestore.Client()

# Initialize keypad
factory = rpi_gpio.KeypadFactory()
keypad = factory.create_keypad(keypad=KEYPAD_KEYS, row_pins=KEYPAD_ROWS, col_pins=KEYPAD_COLS)

#  FUNCTIONS 

def get_pin_input(length=4):
    """Read a fixed-length PIN from the keypad."""
    pin = ""
    def key_handler(key):
        nonlocal pin
        if key in ["A","B","C","D","*","#"]:
            return
        print(key, end="", flush=True)
        pin += key
        if len(pin) >= length:
            keypad.unregisterKeyPressHandler(key_handler)
    print("Enter PIN:", end=" ", flush=True)
    keypad.registerKeyPressHandler(key_handler)
    while len(pin) < length:
        time.sleep(0.1)
    print()
    return pin


def detect_face_gray(image):
    """Detect the first face in a grayscale image and return the ROI."""
    faces = face_cascade.detectMultiScale(image, scaleFactor=1.1, minNeighbors=5)
    if len(faces) == 0:
        return None
    x, y, w, h = faces[0]
    return image[y:y+h, x:x+w]


def capture_face_gray():
    """Capture a single frame from the Pi camera via OpenCV and return a face ROI in grayscale."""
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        raise RuntimeError("Cannot open camera")
    ret, frame = cap.read()
    cap.release()
    if not ret:
        raise RuntimeError("Failed to capture image")
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    face = detect_face_gray(gray)
    if face is None:
        raise ValueError("No face detected in live image")
    return face


def log_access(user_id, pin, success):
    """Log access locally and to Firestore."""
    timestamp = datetime.utcnow().isoformat()
    entry = {"timestamp": timestamp, "pin_entered": pin, "user_id": user_id, "success": success}
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")
    db.collection(LOG_COLLECTION).add(entry)

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
        # Load and detect face in stored image
        img = cv2.imread(user['local_image_path'], cv2.IMREAD_GRAYSCALE)
        stored_face = detect_face_gray(img)
        if stored_face is None:
            raise ValueError("No face detected in stored image")

        # Capture and detect live face
        live_face = capture_face_gray()

        # Train LBPH recognizer on stored face
        recognizer = cv2.face.LBPHFaceRecognizer_create()
        recognizer.train([stored_face], np.array([0]))  # label '0'

        # Predict on live face
        label, confidence = recognizer.predict(live_face)
        match = (confidence <= FACE_CONFIDENCE_THRESHOLD)
    except Exception as e:
        print(f"Face verification failed: {e}")
        log_access(user['id'], pin, False)
        return

    if match:
        print("Access granted")
        log_access(user['id'], pin, True)
    else:
        print(f"Access denied: face mismatch (confidence={confidence:.2f})")
        log_access(user['id'], pin, False)

if __name__ == "__main__":
    main()