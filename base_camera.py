import time
import threading

class CameraEvent(object):
    def __init__(self):
        self.events = {}

    def wait(self):
        ident = threading.get_ident()
        if ident not in self.events:
            self.events[ident] = [threading.Event(), time.time()]
        return self.events[ident][0].wait()

    def set(self):
        now = time.time()
        remove = []
        for ident, event in self.events.items():
            if not event[0].is_set():
                event[0].set()
                event[1] = now
            else:
                if now - event[1] > 5:
                    remove.append(ident)
        for ident in remove:
            del self.events[ident]

    def clear(self):
        self.events[threading.get_ident()][0].clear()

class BaseCamera(object):
    thread = None 
    frame = None 
    last_access = 0 
    event = CameraEvent()

    def __init__(self):
        if BaseCamera.thread is None:
            BaseCamera.last_access = time.time()
            BaseCamera.thread = threading.Thread(target=self._thread)
            BaseCamera.thread.start()

            while self.get_frame() is None:
                time.sleep(0)

    def get_frame(self):
        BaseCamera.last_access = time.time()

        if BaseCamera.thread is None:
            print("Client connected. Waking up camera thread...")
            BaseCamera.thread = threading.Thread(target=self._thread)
            BaseCamera.thread.start()

        BaseCamera.event.wait()
        BaseCamera.event.clear()
        return BaseCamera.frame

    @classmethod
    def _thread(cls):
        print('Starting camera thread.')
        try:
            frames_iterator = cls.frames()
            for frame in frames_iterator:
                BaseCamera.frame = frame
                BaseCamera.event.set()
                time.sleep(0)

                if time.time() - BaseCamera.last_access > 10:
                    print('Stopping camera thread due to inactivity.')
                    break
            
            frames_iterator.close() 
            
        except Exception as e:
            print(f"Internal Camera Thread Error: {e}")
            
        finally:
            BaseCamera.thread = None
            print("Camera thread fully exited.")