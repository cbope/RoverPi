import threading
import time
from flask import Flask, render_template, Response
from flask_socketio import SocketIO
from gpiozero import Motor
from board import SCL, SDA
import busio
from adafruit_motor import servo
from adafruit_pca9685 import PCA9685
from camera_pi2 import Camera

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# --- HARDWARE SETUP (Same as before) ---
i2c = busio.I2C(SCL, SDA)
pca = PCA9685(i2c, address=0x40)
pca.frequency = 50
pan_servo = servo.Servo(pca.channels[0], min_pulse=500, max_pulse=2400, actuation_range=180)
tilt_servo = servo.Servo(pca.channels[1], min_pulse=500, max_pulse=2400, actuation_range=180)
motor_left = Motor(forward=27, backward=18, enable=17)
motor_right = Motor(forward=26, backward=21, enable=4)

# --- GLOBAL STATE ---
MAX_MOTOR_SPEED = 0.5
target_pan, target_tilt = 90.0, 90.0
current_pan, current_tilt = 90.0, 90.0
SMOOTHING_FACTOR = 0.3 # Snappier for head-tracking

# --- WEBSOCKET HANDLER (The Quest Link) ---
@socketio.on('robot_cmd')
def handle_robot_cmd(data):
    global target_pan, target_tilt
    
    # Driving (from Quest Thumbstick)
    joy_x = data.get('x', 0)
    joy_y = data.get('y', 0)
    
    l_speed = max(min(joy_y + joy_x, 1.0), -1.0) * MAX_MOTOR_SPEED
    r_speed = max(min(joy_y - joy_x, 1.0), -1.0) * MAX_MOTOR_SPEED
    
    if abs(l_speed) > 0.05:
        motor_left.forward(l_speed) if l_speed > 0 else motor_left.backward(abs(l_speed))
    else: motor_left.stop()

    if abs(r_speed) > 0.05:
        motor_right.forward(r_speed) if r_speed > 0 else motor_right.backward(abs(r_speed))
    else: motor_right.stop()

    # Head Tracking (from Quest IMU)
    # Mapping VR degrees (often -90 to 90) to Servo (0 to 180)
    target_pan = data.get('head_yaw', 0) + 90
    target_tilt = data.get('head_pitch', 0) + 90

# --- SERVO SMOOTHING THREAD ---
def servo_loop():
    global current_pan, current_tilt
    while True:
        current_pan += (target_pan - current_pan) * SMOOTHING_FACTOR
        current_tilt += (target_tilt - current_tilt) * SMOOTHING_FACTOR
        pan_servo.angle = max(min(current_pan, 160), 20)
        tilt_servo.angle = max(min(current_tilt, 160), 20)
        time.sleep(0.02)

# (Add your standard Flask routes / and /video_feed here)

if __name__ == '__main__':
    threading.Thread(target=servo_loop, daemon=True).start()
    socketio.run(app, host='0.0.0.0', port=5000)