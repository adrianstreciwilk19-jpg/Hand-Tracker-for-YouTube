#Na początek do wykonania w konsoli:
# py -m pip install keyboard
# py -m pip install pyautogui
# py -m pip install opencv-python mediapipe  

import cv2
import mediapipe as mp
import pyautogui
import time
import keyboard

from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from collections import deque

#=====================
#KONFIGURACJA
#=====================
model_path = r"C:\Python\MyProjects\HandTracker\models\hand_landmarker.task"

SWIPE_THRESHOLD = 100
STILL_THRESHOLD_X = 40
STILL_THRESHOLD_Y = 40  # max ruch uznawany za stanie w miejscu
STILL_TIME = 0.5      # ile sekund ma stać w miejscu
ACTION_COOLDOWN = 1.0 # odstęp pomiędzy akcjami
waiting_for_reset = False
RESET_STILL_TIME = 0.4
reset_start = None
RESET_BLOCK_TIME = 0.8
block_until = 0

pozycje_x = deque(maxlen=6)
pozycje_y = deque(maxlen=6)

#fail-safe PyAutoGUI - ruszenie myszą do rogu może przerwać automatykę
pyautogui.FAILSAFE = True

# ======================
# MEDIAPIPE
# ======================

base_options = python.BaseOptions(model_asset_path=model_path)
options = vision.HandLandmarkerOptions(
    base_options=base_options,
    num_hands=1
)
detector = vision.HandLandmarker.create_from_options(options)

# ======================
# KAMERA
# ======================
kamera = cv2.VideoCapture(0, cv2.CAP_DSHOW)

# ======================
# ZMIENNE STANU
# ======================

prev_x = None
prev_y = None
still_start = None
last_action_time = 0

def czy_otwarta_dlon(dlon):
    # indeksy landmarków:
    # wskazujący: tip 8, pip 6
    # środkowy:   tip 12, pip 10
    # serdeczny:  tip 16, pip 14
    # mały:       tip 20, pip 18

    palce_w_gorze = 0
    if dlon[8].y < dlon[6].y:
        palce_w_gorze += 1
    if dlon[12].y < dlon[10].y:
        palce_w_gorze += 1
    if dlon[16].y < dlon[14].y:
        palce_w_gorze += 1
    if dlon[20].y < dlon[18].y:
        palce_w_gorze += 1

    return palce_w_gorze >= 4
while True:
    ret, klatka = kamera.read()
    if not ret:
        print("Brak Obrazu")
        break
    #lustrzane odbicie, wygodniejsze do sterowania
    klatka = cv2.flip(klatka, 1)

    rgb = cv2.cvtColor(klatka, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

    wynik = detector.detect(mp_image)

    wysokosc, szerokosc, _ = klatka.shape
    teraz = time.time()
    # if teraz < block_until:
    #     cv2.imshow("Hand Tracker YouTube Control", klatka)
    #     if cv2.waitKey(1) == ord('q'):
    #         break
    #     continue

    if wynik.hand_landmarks:
        #pobranie dla pierwszej wykrytej dłoni
        dlon = wynik.hand_landmarks[0]

        # landmark 0 = nadgarstek, 9 = środek dłoni / środkowy palec u podstawy
        # jako punkt sterujący użyjemy 9, bo zwykle jest stabilniejszy

        punkt = dlon[9]

        x = int(punkt.x * szerokosc)
        y = int(punkt.y * wysokosc)

        #punkt sterujący
        cv2.circle(klatka, (x,y), 10, (0, 255, 0), -1)
        cv2.putText(klatka, f"X:{x} Y:{y}", (x + 10, y - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        
        pozycje_x.append(x)
        pozycje_y.append(y)

        if len(pozycje_x) >= 6:
            dx = pozycje_x[-1] - pozycje_x[0]
            dy = pozycje_y[-1] - pozycje_y[0]

            #print(f"dx={dx}, dy={dy}")

            # =======================
            # TRYB RESETU PO AKCJI
            # =======================
            if waiting_for_reset:
                if abs(dx) < STILL_THRESHOLD_X and abs(dy) < STILL_THRESHOLD_Y:
                    if reset_start is None:
                        reset_start = teraz
                    if reset_start is not None and (teraz - reset_start) >= RESET_STILL_TIME:
                        waiting_for_reset = False
                        reset_start = None
                        pozycje_x.clear()
                        pozycje_y.clear()
                        still_start = None
                        print("Reset gotowy")
                    else:
                        reset_start = None                
            else:
                # 1) machnięcie w prawo -> 10s do przodu
                if czy_otwarta_dlon(dlon) and dx > SWIPE_THRESHOLD and (teraz - last_action_time) > ACTION_COOLDOWN:
                    pyautogui.press('l')
                    print(">>>>")
                    last_action_time = teraz
                    block_until = teraz + RESET_BLOCK_TIME
                    still_start = None
                    pozycje_x.clear()
                    pozycje_y.clear()

                # 2) machnięcie w lewo -> 10s do tyły
                elif czy_otwarta_dlon(dlon) and dx < -SWIPE_THRESHOLD and (teraz - last_action_time) > ACTION_COOLDOWN:
                    pyautogui.press('j')
                    print("<<<<")
                    last_action_time = teraz
                    block_until = teraz + RESET_BLOCK_TIME
                    still_start = None
                    #reset_start = None
                    pozycje_x.clear()
                    pozycje_y.clear()

                # 3) dłoń w miejscu -> pauza / play
                
                
                elif czy_otwarta_dlon(dlon) and abs(dx) < STILL_THRESHOLD_X and abs(dy) < STILL_THRESHOLD_Y:
                    if still_start is None:
                        still_start = teraz
                    elif (teraz - still_start) >= STILL_TIME and (teraz - last_action_time) > ACTION_COOLDOWN:     
                        pyautogui.press('k')
                        print("PAUZA / PLAY")
                        last_action_time = teraz
                        #waiting_for_reset = True
                        block_until = teraz + RESET_BLOCK_TIME
                        still_start = None
                        #reset_start = None
                        pozycje_x.clear()
                        pozycje_y.clear()
                else:
                    still_start = None
                    reset_start = None
                    waiting_for_reset = False
                    pozycje_x.clear()
                    pozycje_y.clear()

        prev_x = x
        prev_y = y


    else:
        prev_x = None
        prev_y = None
        still_start = None

    # cv2.imshow("Hand Tracker YouTube Control", klatka)

    # if cv2.waitKey(1) == ord('q'):
    #     break
    if keyboard.is_pressed('q'):
        break

kamera.release()
#kcv2.destroyAllWindows()
