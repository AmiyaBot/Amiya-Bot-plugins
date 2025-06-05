import os
from io import BytesIO
from PIL import Image, ImageDraw
from .logger import debug_log


curr_dir = os.path.dirname(__file__)


def create_gacha_image(result: list):
    image = Image.open(f'{curr_dir}/../gacha/bg.png')
    draw = ImageDraw.ImageDraw(image)

    x = 78
    for item in result:
        if item is None:
            x += 82
            continue

        rarity = f'{curr_dir}/../gacha/%s.png' % item['rarity']
        if os.path.exists(rarity):
            img = Image.open(rarity).convert('RGBA')
            image.paste(img, box=(x, 0), mask=img)

        portrait = item['portrait']

        debug_log(f"item is {item}")

        if portrait and os.path.exists(portrait):
            img = Image.open(portrait).convert('RGBA')

            radio = 252 / img.size[1]

            width = int(img.size[0] * radio)
            height = int(img.size[1] * radio)

            step = int((width - 82) / 2)
            crop = (step, 0, width - step, height)

            img = img.resize(size=(width, height))
            img = img.crop(crop)
            image.paste(img, box=(x, 112), mask=img)

        draw.rectangle((x + 10, 321, x + 70, 381), fill='white')
        class_img = f'{curr_dir}/../classify/%s.png' % item['class']
        if os.path.exists(class_img):
            img = Image.open(class_img).convert('RGBA')
            img = img.resize(size=(59, 59))
            image.paste(img, box=(x + 11, 322), mask=img)

        x += 82

    x, y = image.size
    image = image.resize((int(x * 0.8), int(y * 0.8)), Image.ANTIALIAS)

    container = BytesIO()
    image.save(container, quality=80, format='PNG')

    return container.getvalue()
