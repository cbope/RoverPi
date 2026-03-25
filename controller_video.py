import os
import time
import threading
import evdev
from evdev import InputDevice, ecodes
from flask import Flask, render_template, Response

# Hardware Imports
from gpiozero import Motor
from board import SCL, SDA
import busio
from adafruit_motor import servo
from adafruit_pca9685 import PCA9685

# Import your specific camera module
from camera_pi2 import Camera

app = Flask(__name__)

# --- ROBOT CONFIGURATION ---
MAX_MOTOR_SPEED = 0.5 
SMOOTHING_FACTOR = 0.25 
MIN_ANGLE = 0
MAX_ANGLE = 180

# --- HARDWARE INITIALIZATION ---
# I2C and Servos
i2c = busio.I2C(SCL, SDA)
pca = PCA9685(i2c, address=0x40)
pca.frequency = 50

pan_servo = servo.Servo(pca.channels[0], min_pulse=500, max_pulse=2400, actuation_range=180)
tilt_servo = servo.Servo(pca.channels[1], min_pulse=500, max_pulse=2400, actuation_range=180)

# Motors
motor_left = Motor(forward=27, backward=18, enable=17)
motor_right = Motor(forward=26, backward=21, enable=4)

# --- FLASK ROUTES (The "Eyes") ---
@app.route('/')
def index():
    return render_template('index.html')

def gen(camera):
    yield b'--frame\r\n'
    while True:
        frame = camera.get_frame()
        yield b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n--frame\r\n'

@app.route('/video_feed')
def video_feed():
    return Response(gen(Camera()),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

# --- ROBOT CONTROL LOOP (The "Brain") ---
def robot_control_loop():
    print("Robot Control Thread Starting...")
    DEVICE_NAME = "8BitDo Lite 2"
    DEVICE_PATH = "/dev/input/event4"

    def find_device():
        devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
        for device in devices:
            if DEVICE_NAME in device.name:
                return device.path
        return None

    # State trackers
    l_axis_states = {'ABS_X': 127, 'ABS_Y': 127}
    r_axis_states = {'ABS_Z': 127, 'ABS_RZ': 127}
    current_pan = 90.0
    current_tilt = 90.0

    while True:
        try:
            path = find_device() or DEVICE_PATH
            gamepad = InputDevice(path)
            gamepad.grab()
            print(f"Gamepad Connected: {gamepad.name}")

            while True:
                # 1. Capture Gamepad Events
                while True:
                    event = gamepad.read_one()
                    if event is None: break 
                    if event.type == ecodes.EV_ABS:
                        if event.code == ecodes.ABS_X: l_axis_states['ABS_X'] = event.value
                        elif event.code == ecodes.ABS_Y: l_axis_states['ABS_Y'] = event.value
                        elif event.code == ecodes.ABS_Z: r_axis_states['ABS_Z'] = event.value
                        elif event.code == ecodes.ABS_RZ: r_axis_states['ABS_RZ'] = event.value

                # 2. Process Driving (Speed Limited)
                joy_x = (l_axis_states['ABS_X'] - 127) / 127
                joy_y = -((l_axis_states['ABS_Y'] - 127) / 127)
                
                l_speed = max(min(joy_y + joy_x, 1.0), -1.0) * MAX_MOTOR_SPEED
                r_speed = max(min(joy_y - joy_x, 1.0), -1.0) * MAX_MOTOR_SPEED
                
                if abs(l_speed) > 0.02:
                    if l_speed > 0: motor_left.forward(l_speed)
                    else: motor_left.backward(abs(l_speed))
                else: motor_left.stop()

                if abs(r_speed) > 0.02:
                    if r_speed > 0: motor_right.forward(r_speed)
                    else: motor_right.backward(abs(r_speed))
                else: motor_right.stop()

                # 3. Process Camera (Smooth Motion)
                target_pan = -((r_axis_states['ABS_Z'] - 127) / 127 + 1) / 2 * 180
                target_tilt = -((r_axis_states['ABS_RZ'] - 127) / 127 + 1) / 2 * 180
                
                # We reuse the logic from your working script
                joy_z = -((r_axis_states['ABS_Z'] - 127) / 127)
                joy_rz = -((r_axis_states['ABS_RZ'] - 127) / 127)
                
                t_pan = ((joy_z + 1) / 2 * 180)
                t_tilt = ((joy_rz + 1) / 2 * 180)

                current_pan += (t_pan - current_pan) * SMOOTHING_FACTOR
                current_tilt += (t_tilt - current_tilt) * SMOOTHING_FACTOR

                pan_servo.angle = max(min(current_pan, MAX_ANGLE), MIN_ANGLE)
                tilt_servo.angle = max(min(current_tilt, MAX_ANGLE), MIN_ANGLE)

                time.sleep(0.02)

        except Exception as e:
            print(f"Control Loop Error: {e}. Retrying...")
            motor_left.stop()
            motor_right.stop()
            time.sleep(3)

# --- START EVERYTHING ---
if __name__ == '__main__':
    # 1. Start the Robot Control in the background (Daemon thread)
    robot_thread = threading.Thread(target=robot_control_loop, daemon=True)
    robot_thread.start()

    # 2. Start the Flask Server in the foreground
    # host='0.0.0.0' makes it accessible on your local network
    app.run(host='0.0.0.0', port=5000, threaded=True, debug=False)