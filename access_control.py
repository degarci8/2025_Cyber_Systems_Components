import RPi.GPIO as GPIO
import time
import subprocess
import sys
import json
import socket
from datetime import datetime
from google.cloud import pubsub_v1

# Keypad layout
KEYPAD = [
    ['1','2','3','A'],
    ['4','5','6','B'],
    ['7','8','9','C'],
    ['*','0','#','D']
]

ROW_PINS = [17, 27, 22, 5]
COL_PINS = [23, 24, 25, 16]

# Simulated authorized users (PINs)
authorized_users = {
    "1234": "Alice",
    "4321": "Bob"
}

PROJECT_ID = "your-gcp-project-id"
TOPIC_ID = "your-topic-id"

input_code = ""

publisher = pubsub_v1.PublisherClient()
topic_path = publisher.topic_path(PROJECT_ID, TOPIC_ID)

def setup():
    GPIO.setmode(GPIO.BCM)
    for row_pin in ROW_PINS:
        GPIO.setup(row_pin, GPIO.OUT)
        GPIO.output(row_pin, GPIO.LOW)
    for col_pin in COL_PINS:
        GPIO.setup(col_pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

def gather_system_info():
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "hostname": socket.gethostname(),
        "ip_address": socket.gethostbyname(socket.gethostname())
    }

def publish_log(data):
    try:
        json_data = json.dumps(data).encode("utf-8")
        future = publisher.publish(topic_path, json_data)
        print(f"Published message ID: {future.result()}")
    except Exception as e:
        print(f"Failed to publish to Pub/Sub: {e}")

def take_photo():
    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    filename = f"/home/pi/picture_{timestamp}.jpg"
    try:
        subprocess.run(["libcamera-still", "-o", filename], check=True)
        print(f"Photo saved to {filename}")
    except subprocess.CalledProcessError:
        print("Failed to take photo.")
    return filename

def cleanup_and_exit():
    print("Cleaning up and exiting...")
    GPIO.cleanup()
    sys.exit(0)

def read_keypad():
    global input_code
    for row_index, row_pin in enumerate(ROW_PINS):
        GPIO.output(row_pin, GPIO.HIGH)
        for col_index, col_pin in enumerate(COL_PINS):
            if GPIO.input(col_pin) == GPIO.HIGH:
                key = KEYPAD[row_index][col_index]
                print(f"Key Pressed: {key}")
                if key in "0123456789":
                    input_code += key
                    print(f"Entered: {input_code}")
                    if input_code in authorized_users:
                        print("Correct code. Taking photo...")
                        time.sleep(1)
                        filename = take_photo()
                        data = gather_system_info()
                        data.update({
                            "user": authorized_users[input_code],
                            "pin_entered": input_code,
                            "access": "granted",
                            "photo_path": filename
                        })
                        publish_log(data)
                    elif len(input_code) >= 4:
                        print("Access denied.")
                        data = gather_system_info()
                        data.update({
                            "user": None,
                            "pin_entered": input_code,
                            "access": "denied"
                        })
                        publish_log(data)
                        input_code = ""
                elif key == '*':
                    print("Input cleared.")
                    input_code = ""
                elif key == '#':
                    print("Manual exit key pressed.")
                    cleanup_and_exit()
                time.sleep(0.3)
        GPIO.output(row_pin, GPIO.LOW)

def main():
    try:
        setup()
        print("Enter the passcode using the keypad.")
        print("Press '*' to clear input, '#' to quit.")
        while True:
            read_keypad()
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("Keyboard Interrupt. Exiting...")
        cleanup_and_exit()

if __name__ == '__main__':
    main()
