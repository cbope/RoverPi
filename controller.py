#Controls RoverPi with a gamepad using evdev for input, gpiozero for motor control, and adafruit libraries for servo control.
#Left analog stick controls forward, backward, and turning.
#Right analog stick controls up/down, left/right for the camera servos.

#import evdev for gamepad input
from evdev import InputDevice, ecodes

#import gpiozero for motor control and time
import time
from gpiozero import Motor, OutputDevice

#import board and adafruit libraries for servo control
from board import SCL, SDA
import busio
from adafruit_motor import servo
from adafruit_pca9685 import PCA9685

#Setup servo control
i2c =busio.I2C(SCL, SDA)
#Create asimple PCA9685 class instance.
pca =PCA9685(i2c, address=0x40) #default 0x40
pca.frequency = 50

def set_angle(ID, angle):
    servo_angle = servo.Servo(pca.channels[ID], min_pulse=500, max_pulse=2400, actuation_range=180)
    servo_angle.angle = angle

#Motor Pin Setup
Motor_A_EN    = 4
Motor_B_EN    = 17

Motor_A_Pin1  = 26
Motor_A_Pin2  = 21
Motor_B_Pin1  = 27
Motor_B_Pin2  = 18

Dir_forward   = 1
Dir_backward  = 0

left_forward  = 1
left_backward = 0

right_forward = 0
right_backward= 1

speed_set = 40

#Motor Object and direction setup
motor_left = Motor(forward=Motor_B_Pin1, backward=Motor_B_Pin2, enable=Motor_B_EN)
motor_right = Motor(forward=Motor_A_Pin1, backward=Motor_A_Pin2, enable=Motor_A_EN)

def motorStop():#Motor stops
    motor_left.stop()
    motor_right.stop()


# Connect to your gamepad
gamepad = InputDevice('/dev/input/event4')

# Track left stick axis states (assuming 0-255 range, 127 center)
l_axis_states = {'ABS_X': 127, 'ABS_Y': 127}

# Track right stick axis states (assuming 0-255 range, 127 center)
r_axis_states = {'ABS_Z': 127, 'ABS_RZ': 127}

for event in gamepad.read_loop():
    if event.type == ecodes.EV_ABS:
        # Map specific codes to our state tracker
        if event.code == ecodes.ABS_X:
            l_axis_states['ABS_X'] = event.value
        elif event.code == ecodes.ABS_Y:
            l_axis_states['ABS_Y'] = event.value
        if event.code == ecodes.ABS_Z:
            r_axis_states['ABS_Z'] = event.value
        elif event.code == ecodes.ABS_RZ:
            r_axis_states['ABS_RZ'] = event.value
            
    elif event.type == ecodes.EV_SYN and event.code == ecodes.SYN_REPORT:
        # Normalize inputs (-1.0 to 1.0)
        # Note: Often Y is inverted on controllers (up is negative), 
        # so we multiply by -1 if needed.
        joy_x = (l_axis_states['ABS_X'] - 127) / 127
        joy_y = -((l_axis_states['ABS_Y'] - 127) / 127) # Inverting Y for intuitive control
        joy_z = -((r_axis_states['ABS_Z'] - 127) / 127) # Inverting Z for intuitive control
        joy_rz = -((r_axis_states['ABS_RZ'] - 127) / 127) # Inverting Y for intuitive control
        
        # Deadzone to prevent "creeping" if joystick doesn't center perfectly
        if abs(joy_x) < 0.1: joy_x = 0
        if abs(joy_y) < 0.1: joy_y = 0
        if abs(joy_z) < 0.1: joy_z = 0
        if abs(joy_rz) < 0.1: joy_rz = 0

        # Calculate Drive and Turn
        # Drive is the forward/backward component
        # Turn is the left/right component
        left_speed = joy_y + joy_x
        right_speed = joy_y - joy_x


        # Constrain values to -1.0 to 1.0 range
        left_speed = max(min(left_speed, 1.0), -1.0)
        right_speed = max(min(right_speed, 1.0), -1.0)
        joy_z = max(min(joy_z, 1.0), -1.0)
        joy_rz = max(min(joy_rz, 1.0), -1.0)

        print(f"Left Speed: {left_speed:.2f}, Right Speed: {right_speed:.2f}")
        print(f"Camera Pan (Z): {joy_z:.2f}, Camera Tilt (RZ): {joy_rz:.2f}")


        # Apply to Left Motor
        if left_speed > 0:
            motor_left.forward(left_speed)
        elif left_speed < 0:
            motor_left.backward(abs(left_speed))
        else:
            motor_left.stop()

        # Apply to Right Motor
        if right_speed > 0:
            motor_right.forward(right_speed)
        elif right_speed < 0:
            motor_right.backward(abs(right_speed))
        else:
            motor_right.stop()

        # Apply to Camera Servos
        # Assuming joy_z controls pan (servo 0) and joy_rz controls tilt (servo 1)
        # Map from -1.0 to 1.0 range to 0 to 180 degrees
        pan_angle = int((joy_z + 1) / 2 * 180)  # Map -1 to 1 -> 180 to 0
        tilt_angle = int((joy_rz + 1) / 2 * 180) # Map -1 to 1 -> 0 to 180
        set_angle(0, pan_angle)
        set_angle(1, tilt_angle)
       