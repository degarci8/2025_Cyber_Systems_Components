import RPi.GPIO as GPIO
import time

# Keypad button layout
KEYPAD = [
    ['1','2','3','A'],
    ['4','5','6','B'],
    ['7','8','9','C'],
    ['*','0','#','D']
]

# GPIO pin setup
ROW_PINS = [17, 27, 22, 5]    # R1, R2, R3, R4
COL_PINS = [23, 24, 25, 16]   # C1, C2, C3, C4

def setup():
    GPIO.setmode(GPIO.BCM)
    
    for row_pin in ROW_PINS:
        GPIO.setup(row_pin, GPIO.OUT)
        GPIO.output(row_pin, GPIO.LOW)

    for col_pin in COL_PINS:
        GPIO.setup(col_pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

def read_keypad():
    for row_index, row_pin in enumerate(ROW_PINS):
        GPIO.output(row_pin, GPIO.HIGH)
        for col_index, col_pin in enumerate(COL_PINS):
            if GPIO.input(col_pin) == GPIO.HIGH:
                key = KEYPAD[row_index][col_index]
                print(f"Key Pressed: {key}")
                time.sleep(0.3)  # Debounce delay
        GPIO.output(row_pin, GPIO.LOW)

def main():
    try:
        setup()
        print("Press keys on the keypad (CTRL+C to exit)...")
        while True:
            read_keypad()
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        GPIO.cleanup()

if __name__ == '__main__':
    main()
