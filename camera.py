import cv2

class Camera:
    def __init__(self, source=0):
        """
        Initialize the camera.
        source=0 is usually the built-in laptop webcam or default USB camera.
        """
        self.cap = cv2.VideoCapture(0, cv2.CAP_MSMF)
        if not self.cap.isOpened():
            raise Exception("Could not open video device {}".format(source))

        # Fix Camera Buffering & Reduce Processing Load
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 480)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 360)

    def get_frame(self):
        """
        Capture a frame from the camera.
        Returns the frame (numpy array) if successful, otherwise None.
        """
        ret, frame = self.cap.read()
        if ret:
            return frame
        return None

    def release(self):
        """
        Release the camera resource.
        """
        if self.cap.isOpened():
            self.cap.release()
