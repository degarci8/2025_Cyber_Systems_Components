#!/usr/bin/env python3
"""
access_control.py

Edge device access control using OpenCV LBPH recognizer:
- Prompt for 4-digit PIN via manual keypad scan
- Match PIN to user data
- Perform face detection/matching on stored vs. live image
- Grant/deny access and log attempts to local file and Pub/Sub
"""
import os
import json
import time
import numpy as np
from datetime import datetime
import cv2
from google.cloud import firestore, pubsub_v1
import RPi.GPIO as GPIO
import subprocess

# Configuration
PROJECT_DIR = "/home/raspberrypi/Projects"
DATA_DIR = os.path.join(PROJECT_DIR, "data")
IMAGE_DIR = os.path.join(DATA_DIR, "images")
USERS_FILE = os.path.join(DATA_DIR, "authorized_users.json")
LOG_DIR = os.path.join(PROJECT_DIR, "logs")
LOG_FILE = os.path.join(LOG_DIR, "access.log")

# Pub/Sub setup (replace with your GCP project ID)
PROJECT_ID = "your-gcp-project-id"
TOPIC_NAME = "access-events"
publisher = pubsub_v1.PublisherClient()
topic_path = publisher.topic_path(PROJECT_ID, TOPIC_NAME)

# Keypad configuration (manual scanning)
KEYPAD_ROWS = [17, 27, 22, 5]
KEYPAD_COLS = [23, 24, 25, 16]
KEYPAD_KEYS = [
    ["1","2","3","A"],
    ["4","5","6","B"],
    ["7","8","9","C"],
    ["*","0","#","D"]
]

# Face recognition parameters
FACE_CONFIDENCE_THRESHOLD = 60.0
face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
)
LOG_COLLECTION = "access_logs"

# Setup directories and services
os.makedirs(LOG_DIR, exist_ok=True)
db = firestore.Client()

# GPIO setup
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
for pin in KEYPAD_ROWS:
    GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
for pin in KEYPAD_COLS:
    GPIO.setup(pin, GPIO.OUT)
    GPIO.output(pin, GPIO.LOW)

# Read PIN by manual keypad scanning
def get_pin_input(length=4):
    pin = ""
    print("Enter PIN:", end=' ', flush=True)
    while len(pin) < length:
        for col_idx, col_pin in enumerate(KEYPAD_COLS):
            GPIO.output(col_pin, GPIO.HIGH)
            for row_idx, row_pin in enumerate(KEYPAD_ROWS):
                if GPIO.input(row_pin) == GPIO.HIGH:
                    key = KEYPAD_KEYS[row_idx][col_idx]
                    print(key, end='', flush=True)
                    pin += key
                    while GPIO.input(row_pin) == GPIO.HIGH:
                        time.sleep(0.05)
                    time.sleep(0.2)
            GPIO.output(col_pin, GPIO.LOW)
        time.sleep(0.05)
    print()
    return pin

# Detect face ROI in grayscale image
def detect_face_gray(image):
    faces = face_cascade.detectMultiScale(image, 1.1, 5)
    if len(faces) == 0:
        return None
    x, y, w, h = faces[0]
    return image[y:y+h, x:x+w]

# Capture face ROI from camera with fallback methods
def capture_face_gray():
    # Try Picamera2 first
    try:
        from picamera2 import Picamera2
        picam2 = Picamera2()
        cfg = picam2.create_still_configuration(main={"size":(640,480)})
        picam2.configure(cfg)
        picam2.start()
        time.sleep(0.1)
        frame = picam2.capture_array()
        picam2.stop()
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        face = detect_face_gray(gray)
        if face is not None:
            return face
    except Exception:
        pass
    # Fallback to OpenCV VideoCapture
    cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
    if not cap.isOpened():
        cap = cv2.VideoCapture(0)
    if cap.isOpened():
        ret, frame = cap.read()
        cap.release()
        if ret:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            face = detect_face_gray(gray)
            if face is not None:
                return face
    # Final fallback: libcamera-jpeg
    tmp = os.path.join(PROJECT_DIR, 'capture.jpg')
    try:
        subprocess.run(["libcamera-jpeg","-o",tmp,"-n"], check=True)
        img = cv2.imread(tmp, cv2.IMREAD_GRAYSCALE)
        face = detect_face_gray(img)
        if face is not None:
            return face
    except Exception:
        pass
    return None

# Log access attempts (local and Pub/Sub)
def log_access(user_id, pin, success):
    ts = datetime.utcnow().isoformat()  # high-resolution timestamp
    entry = {
        "user_id": user_id,
        "timestamp": ts,
        "pin_entered": pin,
        "access_result": success
    }
    # Local log
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")
    # Publish to Pub/Sub
    try:
        data = json.dumps(entry).encode('utf-8')
        future = publisher.publish(topic_path, data)
        print(f"Published to Pub/Sub: message id {future.result()}")
    except Exception as e:
        print(f"Warning: Failed to publish to Pub/Sub: {e}")

# Main function
def main():
    with open(USERS_FILE) as f:
        users = {str(u['pin']): u for u in json.load(f)}
    pin = get_pin_input()
    user = users.get(pin)
    if not user:
        print("Access denied: PIN not recognized")
        log_access(None, pin, False)
        return
    print(f"User {user['name']} ({user['id']}) PIN valid")

    # Stored face
    img = cv2.imread(user['local_image_path'], cv2.IMREAD_GRAYSCALE)
    stored_face = detect_face_gray(img) if img is not None else None
    if stored_face is None:
        print("Face verification skipped: no stored face")
        log_access(user['id'], pin, False)
        return

    # Live face
    live_face = capture_face_gray()
    if live_face is None:
        print("Face verification skipped: live capture error")
        log_access(user['id'], pin, False)
        return

    # LBPH matching
    recognizer = cv2.face.LBPHFaceRecognizer_create()
    recognizer.train([stored_face], np.array([0]))
    _, conf = recognizer.predict(live_face)
    print(f"DEBUG: confidence={conf:.2f}")

    result = conf <= FACE_CONFIDENCE_THRESHOLD
    print("Access granted" if result else "Access denied")
    log_access(user['id'], pin, result)

if __name__ == "__main__":
    main()