import RPi.GPIO as GPIO
import time
import subprocess
import sys

# Keypad layout
KEYPAD = [
    ['1','2','3','A'],
    ['4','5','6','B'],
    ['7','8','9','C'],
    ['*','0','#','D']
]

ROW_PINS = [17, 27, 22, 5]
COL_PINS = [23, 24, 25, 16]

CORRECT_CODE = "1234"
input_code = ""

def setup():
    GPIO.setmode(GPIO.BCM)
    
    for row_pin in ROW_PINS:
        GPIO.setup(row_pin, GPIO.OUT)
        GPIO.output(row_pin, GPIO.LOW)

    for col_pin in COL_PINS:
        GPIO.setup(col_pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

def take_photo():
    print("Correct code entered. Taking a picture in:")
    for i in range(3, 0, -1):
        print(f"{i}...")
        time.sleep(1)
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    filename = f"/home/raspberrypi/picture_{timestamp}.jpg"
    print("Taking photo...")
    try:
        subprocess.run(["libcamera-still", "-o", filename], check=True)
        print(f"Photo saved to {filename}")
    except subprocess.CalledProcessError:
        print("Failed to take photo. Is the camera enabled and working?")
    finally:
        cleanup_and_exit()

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
                    if len(input_code) == len(CORRECT_CODE):
                        if input_code == CORRECT_CODE:
                            take_photo()
                        else:
                            print("Incorrect code")
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
