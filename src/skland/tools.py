import os

curr_dir = os.path.dirname(__file__)


def face_detect(file_name: str, reel_width: int = 1200, cascade_name: str = f'{curr_dir}/lbpcascade_animeface.xml'):
    if not os.path.exists(file_name):
        return []

    pos = []
    try:
        import cv2

        img = cv2.imread(file_name)
        face_cascade = cv2.CascadeClassifier(cascade_name)

        for item in face_cascade.detectMultiScale(img):
            x, y = [int(n) for n in item][:2]
            height, width = img.shape[:2]
            reel_height = height * (reel_width / width)

            pos.append([x / width * reel_width, y / height * reel_height])

    except Exception:
        ...

    return pos
