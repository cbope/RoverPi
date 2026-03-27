import sys
import threading
import time
import json
from flask import Flask, render_template, Response
from flask_socketio import SocketIO
from gpiozero import Motor
from board import SCL, SDA
import busio
from adafruit_motor import servo
from adafruit_pca9685 import PCA9685

# Import your optimized camera class
from camera_pi2 import Camera

app = Flask(__name__)
# Using 'threading' mode for hardware stability with PiCamera2
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# --- CONFIGURATION ---
MAX_MOTOR_SPEED = 0.5 
SMOOTHING_FACTOR = 0.3
SAFETY_TIMEOUT = 2.0  # Seconds of silence before "Parking" the robot
MIN_ANGLE, MAX_ANGLE = 20, 160

# --- HARDWARE INITIALIZATION ---
print("\n--- ROVERPI HARDWARE BOOT ---", flush=True)

try:
    print("[INIT] Initializing Drive Motors...", end="", flush=True)
    motor_left = Motor(forward=27, backward=18, enable=17)
    motor_right = Motor(forward=26, backward=21, enable=4)
    print(" OK", flush=True)

    print("[INIT] Setting up I2C and Servo Board...", end="", flush=True)
    i2c = busio.I2C(SCL, SDA)
    pca = PCA9685(i2c, address=0x40)
    pca.frequency = 50
    pan_servo = servo.Servo(pca.channels[0], min_pulse=500, max_pulse=2400, actuation_range=180)
    tilt_servo = servo.Servo(pca.channels[1], min_pulse=500, max_pulse=2400, actuation_range=180)
    print(" OK", flush=True)

    print("[INIT] Starting PiCamera Hardware...", end="", flush=True)
    robot_camera = Camera()
    print(" OK", flush=True)
except Exception as e:
    print(f"\n[FATAL ERROR] Hardware failed: {e}")
    sys.exit(1)

# --- GLOBAL STATE ---
target_pan, target_tilt = 90.0, 90.0
current_pan, current_tilt = 90.0, 90.0
last_command_time = time.time()
is_parked = True

# --- VIDEO STREAMING ---
def gen(camera):
    while True:
        frame = camera.get_frame()
        if frame:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        else:
            time.sleep(0.01)

@app.route('/video_feed')
def video_feed():
    return Response(gen(robot_camera),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

# --- SOCKETIO CONTROL & SAFETY ---
@socketio.on('connect')
def handle_connect():
    global last_command_time, is_parked
    last_command_time = time.time()
    is_parked = False
    print("[Control] Quest 3 Connected. Control Active.")

@socketio.on('disconnect')
def handle_disconnect():
    global target_pan, target_tilt, is_parked
    print("[Control] Quest 3 Disconnected. Homing Servos...")
    target_pan = 90.0
    target_tilt = 90.0
    motor_left.stop()
    motor_right.stop()
    is_parked = True

@socketio.on('robot_cmd')
def handle_robot_cmd(data):
    global target_pan, target_tilt, last_command_time, is_parked
    
    # Update heartbeat
    last_command_time = time.time()
    is_parked = False

    if isinstance(data, str):
        try: data = json.loads(data)
        except: return

    # 1. Drive Motors
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

    # 2. Head Tracking
    target_pan = data.get('head_yaw', 0) + 90
    target_tilt = data.get('head_pitch', 0) + 90

# --- BACKGROUND SERVO & WATCHDOG THREAD ---
def servo_loop():
    global current_pan, current_tilt, target_pan, target_tilt, is_parked
    
    while True:
        # WATCHDOG CHECK: If silence > SAFETY_TIMEOUT, park the bot
        if not is_parked and (time.time() - last_command_time > SAFETY_TIMEOUT):
            print("[Safety] Signal Lost. Parking Robot...")
            target_pan = 90.0
            target_tilt = 90.0
            motor_left.stop()
            motor_right.stop()
            is_parked = True

        # Interpolation for smooth motion
        current_pan += (target_pan - current_pan) * SMOOTHING_FACTOR
        current_tilt += (target_tilt - current_tilt) * SMOOTHING_FACTOR
        
        # Write to PCA9685
        pan_servo.angle = max(min(current_pan, MAX_ANGLE), MIN_ANGLE)
        tilt_servo.angle = max(min(current_tilt, MAX_ANGLE), MIN_ANGLE)
        
        time.sleep(0.02)

# --- STARTUP ---
if __name__ == '__main__':
    print("\n--- ROVERPI TELEPRESENCE READY ---")
    threading.Thread(target=servo_loop, daemon=True).start()
    
    # Run server
    socketio.run(app, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)