import time
import json
import cv2
import os
import socket
from datetime import datetime
from pad4pi import rpi_gpio
import RPi.GPIO as GPIO
from google.cloud import pubsub_v1

# --- CONFIGURATION ---
CORRECT_CODE = "1234"
FACE_CASCADE_PATH = "/home/pi/haarcascade_frontalface_default.xml"
PUBSUB_TOPIC = "projects/YOUR_PROJECT_ID/topics/YOUR_TOPIC_NAME"
ROW_PINS = [17, 27, 22, 5]
COL_PINS = [23, 24, 25, 16]
KEYPAD = [
    ["1", "2", "3", "A"],
    ["4", "5", "6", "B"],
    ["7", "8", "9", "C"],
    ["*", "0", "#", "D"]
]

# Setup Google Pub/Sub
publisher = pubsub_v1.PublisherClient()
topic_path = PUBSUB_TOPIC

# Setup Face Recognition
face_cascade = cv2.CascadeClassifier(FACE_CASCADE_PATH)

# Setup Keypad
factory = rpi_gpio.KeypadFactory()
keypad = factory.create_keypad(keypad=KEYPAD, row_pins=ROW_PINS, col_pins=COL_PINS)
entered_code = ""

# --- FUNCTIONS ---
def log_access(status, reason):
    log_data = {
        "timestamp": datetime.now().isoformat(),
        "device": socket.gethostname(),
        "access": status,
        "reason": reason
    }
    message_json = json.dumps(log_data).encode("utf-8")
    future = publisher.publish(topic_path, data=message_json)
    print(f"Access {status.upper()} — Reason: {reason}")
    print(f"Log sent to Pub/Sub: {log_data}")

def preview_face():
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Camera failed to open.")
        return None

    print("Showing camera feed... Press 's' to capture.")
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        cv2.imshow("Face Preview", frame)
        if cv2.waitKey(1) & 0xFF == ord('s'):
            break
    cap.release()
    cv2.destroyAllWindows()
    return frame

def validate_face(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, 1.3, 5)
    return len(faces) > 0

def handle_key(key):
    global entered_code
    print(f"Key pressed: {key}")
    if key == "#":
        if entered_code == CORRECT_CODE:
            print("Code correct. Starting camera...")
            frame = preview_face()
            if frame is not None and validate_face(frame):
                print("Face recognized.")
                log_access("granted", "Correct PIN and valid face")
                print("Access Granted! (e.g., unlock door here)")
            else:
                print("Face not recognized.")
                log_access("denied", "Correct PIN, face mismatch")
        else:
            log_access("denied", "Incorrect PIN")
        entered_code = ""
    elif key == "*":
        entered_code = ""
        print("Code cleared.")
    else:
        entered_code += key

keypad.registerKeyPressHandler(handle_key)

# --- MAIN LOOP ---
try:
    print("Enter code on the keypad...")
    while True:
        time.sleep(0.1)
except KeyboardInterrupt:
    print("Exiting...")
    GPIO.cleanup()
