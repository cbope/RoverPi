import evdev
from evdev import InputDevice, ecodes
import time
from gpiozero import Motor
from board import SCL, SDA
import busio
from adafruit_motor import servo
from adafruit_pca9685 import PCA9685

# --- SETUP SERVO CONTROL ---
i2c = busio.I2C(SCL, SDA)
pca = PCA9685(i2c, address=0x40)
pca.frequency = 50

pan_servo = servo.Servo(pca.channels[0], min_pulse=500, max_pulse=2400, actuation_range=180)
tilt_servo = servo.Servo(pca.channels[1], min_pulse=500, max_pulse=2400, actuation_range=180)

# --- CONFIGURATION ---
# Change this to limit your robot's top speed (0.1 to 1.0)
# 0.5 means the robot will only ever reach 50% power
MAX_MOTOR_SPEED = 0.5 

# Servo Smoothing Variables
target_pan = 90.0
target_tilt = 90.0
current_pan = 90.0
current_tilt = 90.0
SMOOTHING_FACTOR = 0.25 

MIN_ANGLE = 20
MAX_ANGLE = 160

# --- MOTOR PIN SETUP ---
motor_left = Motor(forward=27, backward=18, enable=17)
motor_right = Motor(forward=26, backward=21, enable=4)

def motorStop():
    motor_left.stop()
    motor_right.stop()

# --- CONTROLLER SETUP ---
DEVICE_NAME = "8BitDo Lite 2"
DEVICE_PATH = "/dev/input/event4"

def find_device():
    devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
    for device in devices:
        if DEVICE_NAME in device.name:
            return device.path
    return None

l_axis_states = {'ABS_X': 127, 'ABS_Y': 127}
r_axis_states = {'ABS_Z': 127, 'ABS_RZ': 127}

print(f"RoverPi Active. Motor speed limited to {MAX_MOTOR_SPEED*100}%")

while True:
    try:
        path = find_device() or DEVICE_PATH
        gamepad = InputDevice(path)
        gamepad.grab()
        
        while True:
            # Drain event backlog
            while True:
                event = gamepad.read_one()
                if event is None: break 
                
                if event.type == ecodes.EV_ABS:
                    if event.code == ecodes.ABS_X: l_axis_states['ABS_X'] = event.value
                    elif event.code == ecodes.ABS_Y: l_axis_states['ABS_Y'] = event.value
                    elif event.code == ecodes.ABS_Z: r_axis_states['ABS_Z'] = event.value
                    elif event.code == ecodes.ABS_RZ: r_axis_states['ABS_RZ'] = event.value

            # 1. Normalize Stick Inputs
            joy_x = (l_axis_states['ABS_X'] - 127) / 127
            joy_y = -((l_axis_states['ABS_Y'] - 127) / 127)
            joy_z = -((r_axis_states['ABS_Z'] - 127) / 127)
            joy_rz = -((r_axis_states['ABS_RZ'] - 127) / 127)

            # 2. MOTOR LOGIC (Applying the permanent speed limit)
            # We calculate raw speed first, then multiply by our limit
            raw_l = max(min(joy_y + joy_x, 1.0), -1.0)
            raw_r = max(min(joy_y - joy_x, 1.0), -1.0)
            
            l_speed = raw_l * MAX_MOTOR_SPEED
            r_speed = raw_r * MAX_MOTOR_SPEED
            
            # Apply to hardware
            if abs(l_speed) > 0.05:
                if l_speed > 0: motor_left.forward(l_speed)
                else: motor_left.backward(abs(l_speed))
            else: motor_left.stop()

            if abs(r_speed) > 0.05:
                if r_speed > 0: motor_right.forward(r_speed)
                else: motor_right.backward(abs(r_speed))
            else: motor_right.stop()

            # 3. SERVO SMOOTHING
            target_pan = ((joy_z + 1) / 2 * 180)
            target_tilt = ((joy_rz + 1) / 2 * 180)

            current_pan += (target_pan - current_pan) * SMOOTHING_FACTOR
            current_tilt += (target_tilt - current_tilt) * SMOOTHING_FACTOR

            pan_servo.angle = max(min(current_pan, MAX_ANGLE), MIN_ANGLE)
            tilt_servo.angle = max(min(current_tilt, MAX_ANGLE), MIN_ANGLE)

            time.sleep(0.02) # 50Hz Update Rate

    except (OSError, IOError, FileNotFoundError):
        print("Controller lost. Reconnecting...")
        motorStop()
        time.sleep(3)
    except KeyboardInterrupt:
        motorStop()
        break