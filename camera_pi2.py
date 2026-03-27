#!/usr/bin/env/python
# File name   : camera_pi2.py
import io
import time
import cv2
from picamera2 import Picamera2
import libcamera 
from base_camera import BaseCamera

hflip = 0
vflip = 0

class Camera(BaseCamera):
    @staticmethod
    def frames():
        picam2 = Picamera2() 
        
        try:
            # We use Dictionary access here because your library version prefers it
            config = picam2.create_video_configuration()
            config['main']['size'] = (640, 480)
            config['main']['format'] = 'RGB888'
            
            # Setting the transform (hflip/vflip)
            config['transform'] = libcamera.Transform(hflip=hflip, vflip=vflip)
            
            picam2.configure(config)

            if not picam2.is_open:
                raise RuntimeError('Could not start camera.')

            print("[Camera] Powering on sensor...")
            picam2.start()

            while True:
                img = picam2.capture_array()
                
                # Encode to JPEG (50 quality is great for Quest 3 bandwidth)
                encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 50]
                result, encimg = cv2.imencode('.jpg', img, encode_param)
            
                if result:
                    yield encimg.tobytes()
                
                time.sleep(0)

        except Exception as e:
            print(f"\033[38;5;1m[Camera Error]\033[0m: {e}")
        
        finally:
            print("[Camera] Releasing hardware...")
            try:
                picam2.stop()
                picam2.close()
                print("[Camera] Hardware state: Available")
            except:
                pass