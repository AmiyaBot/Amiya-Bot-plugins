import os

curr_dir = os.path.dirname(__file__)


def face_detect(file_name: str, cascade_name: str = f'{curr_dir}/lbpcascade_animeface.xml'):
    if not os.path.exists(file_name):
        return []

    pos = []
    try:
        import cv2

        img = cv2.imread(file_name)
        face_cascade = cv2.CascadeClassifier(cascade_name)

        for item in face_cascade.detectMultiScale(img):
            pos.append([int(n) for n in item])

    except Exception:
        ...

    return pos
