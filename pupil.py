import sys
from PyQt5.QtWidgets import QMainWindow, QApplication, QVBoxLayout, QHBoxLayout, QWidget, QLabel, QTextEdit, QSlider
from PyQt5.QtGui import QPixmap, QImage, QIcon
from PyQt5.QtCore import QTimer, QThread, Qt
import cv2
import numpy as np
from QSharpTools import SharpButton

face_cascade = cv2.CascadeClassifier('haarcascade_frontalface_default.xml')
eye_cascade = cv2.CascadeClassifier('haarcascade_eye.xml')
detector_params = cv2.SimpleBlobDetector_Params()
detector_params.filterByArea = True
detector_params.maxArea = 1500
detector = cv2.SimpleBlobDetector_create(detector_params)

mainImg = QImage()
currentSequence = ""
patterns = {}

def sigmoid(x):
    return 1/(1 + np.exp(-x))

def activation(x):
    a = 45
    b = 18
    c = 50
    return c * (sigmoid(x - a) + sigmoid(x - a - b))

def getFace(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, 1.3, 5)
    if len(faces) < 1:
        return None
    x, y, w, h = faces[0]
    return img[y:y + h, x:x + w]

def getEyes(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    eyes = eye_cascade.detectMultiScale(gray, 1.3, 5)
    if len(eyes) < 1:
        return 0, None, None
    elif len(eyes) < 2:
        x, y, w, h = eyes[0]
        eye1 = img[y:y + h, x:x + w]
        return w, eye1, None
    x, y, w, h = eyes[0]
    eye1 = img[y:y + h, x:x + w]
    x, y, w, h = eyes[1]
    eye2 = img[y:y + h, x:x + w]
    return w, eye1, eye2

def cropBottom(img, fraction = 0.25):
    if fraction > 1.0 or fraction < 0.0:
        print("fraction parameter must be a positive floating point less than 1")
    height, width = img.shape[:2]
    cropHeight = int(height * fraction)
    return img[cropHeight:height, 0:width]

def getBlobs(img, threshold = 90):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, img = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY)
    img = cv2.erode(img, None, iterations = 2)
    img = cv2.dilate(img, None, iterations = 4)
    img = cv2.medianBlur(img, 5)
    keypoints = detector.detect(img)
    return keypoints

def capture():
    global mainImg
    global currentSequence
    queue = []
    queueSize = 6
    resetCount = 0
    resetCap = 65
    threshold_initial = 75
    cropBottomPercent = 0.33
    state = "C"

    videoCapture = cv2.VideoCapture(0)
    cv2.namedWindow("image")
    cv2.createTrackbar("threshold", "image", threshold_initial, 255, lambda x:x)
    while True:
        _, colorCapture = videoCapture.read()
        face = getFace(colorCapture)
        if face is not None:
            eyeWidth, eye1, eye2 = getEyes(face)
            eyes = [eye1, eye2]
            for eye in eyes:
                if eye is not None:
                    th = cv2.getTrackbarPos("threshold", "image")
                    eye = cropBottom(eye, cropBottomPercent)
                    keypoints = getBlobs(eye, th)
                    for keypoint in keypoints:
                        value = (keypoint.pt[0] * 100) / eyeWidth
                        
                        if len(queue) >= queueSize:
                            queue.pop()
                        queue.insert(0, value)
                        
                        act = activation(sum(queue)/len(queue))
                        if act < 25:
                            if state != "R":
                                resetCount = 0
                                state = "R"
                                currentSequence += state
                                myWin.updatePattern()
                                print(currentSequence)
                                #print(state)
                        elif act > 75:
                            if state != "L":
                                resetCount = 0
                                state = "L"
                                currentSequence += state
                                myWin.updatePattern()
                                print(currentSequence)
                                #print(state)
                        else:
                            resetCount += 1
                            if resetCount >= resetCap:
                                resetCount = 0
                                myWin.updateMessage()
                                currentSequence = ""
                                myWin.updatePattern()
                                myWin.updateMessage()
                                print("RESET")
                            if state != "C":
                                state = "C"
                                currentSequence += state
                                myWin.updatePattern()
                                print(currentSequence)
                                #print(state)
                        break
                    cv2.rectangle(eye, (0, 0), (eye.shape[1] - 1, eye.shape[0] - 1), (0, 255, 255))
                    eye = cv2.drawKeypoints(eye, keypoints, eye, (255, 0, 255), cv2.DRAW_MATCHES_FLAGS_DRAW_RICH_KEYPOINTS)
        colorCapture = cv2.flip(colorCapture, 1)
        mainImg = QImage(colorCapture.data, colorCapture.shape[1], colorCapture.shape[0], QImage.Format_RGB888).rgbSwapped()
        _, g = cv2.threshold(cv2.cvtColor(cv2.flip(colorCapture, 1), cv2.COLOR_BGR2GRAY), cv2.getTrackbarPos('threshold', 'image'), 255, cv2.THRESH_BINARY)
        g = cv2.erode(g, None, iterations = 3)
        g = cv2.dilate(g, None, iterations = 4)
        cv2.imshow('image 2', g)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    videoCapture.release()
    cv2.destroyAllWindows()

class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self._width = 680
        self._height = 750
        self._xPos = 600
        self._yPos = 200
        self.initUI()

    def initUI(self):
        global mainImg
        global currentSequence

        self.setGeometry(self._xPos, self._yPos, self._width, self._height)
        self.setWindowTitle("pupil")
        bgColor = (20, 0, 26)
        self.setStyleSheet(f"background-color: rgb{bgColor}")

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.updateFrame)
        self.capThread = captureThread()
        self.capThread.start()
        self.videoOn = False
        self.mainLayout = QHBoxLayout()
        self.vBoxLeft = QVBoxLayout()

        self.hBoxTools = QHBoxLayout()
        self.logoLabel = QLabel()
        self.logoPixmap = QPixmap("img/logo_dark_resized.png")
        self.logoLabel.setPixmap(self.logoPixmap)
        self.hBoxTools.addWidget(self.logoLabel)

        self.recordButton = SharpButton(primaryColor = (128, 0, 96), secondaryColor = (255, 179, 236), parent_background_color = bgColor, border_radius = 5)
        self.recordButton.setIcon(QIcon("img/recordIcon.png"))
        self.recordButton.clicked.connect(self.captureToggle)
        self.hBoxTools.addWidget(self.recordButton)

        self.thresholdDial = QSlider(Qt.Horizontal)
        self.thresholdDial.setMinimum(0)
        self.thresholdDial.setMaximum(255)
        self.thresholdDial.setValue(120)
        self.hBoxTools.addWidget(self.thresholdDial)

        #self.hBoxTools.addStretch(0)

        self.vBoxLeft.addLayout(self.hBoxTools)

        self.patternLabel = QLabel()
        self.patternLabel.setStyleSheet("color: rgb(255, 204, 243); font-size: 25px;")
        self.patternLabel.setText(f" Pattern: {currentSequence}")
        self.vBoxLeft.addWidget(self.patternLabel)

        self.imageLabel = QLabel()
        self.imagePixmap = QPixmap.fromImage(mainImg)
        self.imageLabel.setPixmap(self.imagePixmap)
        self.vBoxLeft.addWidget(self.imageLabel)
        self.vBoxLeft.addStretch(0)

        self.msgEdit = QLabel()
        self.msgEdit.setStyleSheet("color: rgb(255, 204, 243); background-color: black; font-family: Consolas; font-size: 25px;")
        #self.msgEdit.setReadOnly(True)
        self.msgEdit.setText("[Message]")
        self.vBoxLeft.addWidget(self.msgEdit)

        self.mainLayout.addLayout(self.vBoxLeft)
        self.centralWidget = QWidget(self)
        self.centralWidget.setLayout(self.mainLayout)
        self.setCentralWidget(self.centralWidget)

        self.show()
    
    def updateFrame(self):
        global mainImg
        self.imagePixmap = QPixmap.fromImage(mainImg)
        self.imageLabel.setPixmap(self.imagePixmap)

    def updatePattern(self):
        global currentSequence
        self.patternLabel.setText(f" Pattern: {currentSequence}")

    def updateMessage(self):
        global patterns
        global currentSequence
        print("Updating Message: " + currentSequence)
        if currentSequence in patterns:
            print(patterns[currentSequence])
            self.msgEdit.setText(f"Pattern: {currentSequence}, Message: {patterns[currentSequence]}")

    def captureToggle(self):
        global mainImg
        if not self.videoOn:
            self.videoOn = True
            self.timer.start(1)
        else:
            self.videoOn = False
            mainImg = QImage()
            self.updateFrame()
            self.timer.stop()

class captureThread(QThread):
    def __init__(self):
        super().__init__()

    def run(self):
        capture()

if __name__ == "__main__":
    with open("patterns.csv", "r") as patterns_csv:
        for line in patterns_csv.readlines():
            line_split = line.split(",")
            patterns[line_split[0].strip()] = line_split[1].strip()
    app = QApplication(sys.argv)
    myWin = Window()
    sys.exit(app.exec_())