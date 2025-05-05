#!/usr/bin/env python3
"""
access_control.py

Edge device access control using OpenCV LBPH recognizer:
- Prompt for 4-digit PIN via keypad
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
from pad4pi import rpi_gpio
from google.cloud import firestore
import RPi.GPIO as GPIO

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

# Setup directories and services
os.makedirs(LOG_DIR, exist_ok=True)
db = firestore.Client()

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
for pin in KEYPAD_ROWS:
    GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
for pin in KEYPAD_COLS:
    GPIO.setup(pin, GPIO.OUT)
    GPIO.output(pin, GPIO.LOW)

factory = rpi_gpio.KeypadFactory()
keypad = factory.create_keypad(
    keypad=KEYPAD_KEYS,
    row_pins=KEYPAD_ROWS,
    col_pins=KEYPAD_COLS
)

# Function to read PIN input
def get_pin_input(length=4):
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

# Function to detect a face ROI in a grayscale image
def detect_face_gray(image):
    faces = face_cascade.detectMultiScale(image, 1.1, 5)
    if len(faces) == 0:
        return None
    x, y, w, h = faces[0]
    return image[y:y+h, x:x+w]

# Function to capture and return a face ROI from the camera
def capture_face_gray():
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
        raise ValueError("No face detected")
    return face

# Function to log access attempts
def log_access(user_id, pin, success):
    ts = datetime.utcnow().isoformat()
    entry = {"timestamp": ts, "pin_entered": pin, "user_id": user_id, "success": success}
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")
    db.collection(LOG_COLLECTION).add(entry)

# Main access control loop
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
    try:
        img = cv2.imread(user['local_image_path'], cv2.IMREAD_GRAYSCALE)
        stored_face = detect_face_gray(img)
        if stored_face is None:
            raise ValueError("No face in stored image")

        live_face = capture_face_gray()
        recognizer = cv2.face.LBPHFaceRecognizer_create()
        recognizer.train([stored_face], np.array([0]))
        _, conf = recognizer.predict(live_face)
        match = (conf <= FACE_CONFIDENCE_THRESHOLD)
    except Exception as e:
        print(f"Face verification error: {e}")
        log_access(user['id'], pin, False)
        return

    if match:
        print("Access granted")
        log_access(user['id'], pin, True)
    else:
        print(f"Access denied: mismatch (conf={conf:.2f})")
        log_access(user['id'], pin, False)

if __name__ == "__main__":
    main()
