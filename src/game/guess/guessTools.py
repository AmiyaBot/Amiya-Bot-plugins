import random

from PIL import Image
from io import BytesIO


class ImageCropper:
    def __init__(self, path: str, max_transparent_ratio: float = 30.0):
        self.image = Image.open(path)
        self.max_transparent_ratio = max_transparent_ratio

        self.pos = []
        self.size = [
            int(self.image.size[0] * 0.2),
            int(self.image.size[1] * 0.2),
        ]

    @property
    def crop_positions(self):
        if not self.pos:
            self.pos = [
                random.randint(0, self.image.size[0] - self.size[0]),
                random.randint(0, self.image.size[1] - self.size[1]),
            ]

        x, y = self.pos

        return (
            x,
            y,
            x + self.size[0],
            y + self.size[1],
        )

    @classmethod
    def transparent_ratio(cls, image: Image):
        if image.mode != 'RGBA':
            image = image.convert('RGBA')

        total_pixels = image.width * image.height

        transparent_pixels = 0
        for pixel in image.getdata():
            if pixel[3] == 0:
                transparent_pixels += 1

        return transparent_pixels / total_pixels * 100

    def expand(self, size: int):
        if self.pos == [0, 0] and self.size[0] >= self.image.size[0] and self.size[1] >= self.image.size[1]:
            return False

        s = int(size / 2)

        for i, v in enumerate(self.pos):
            self.size[i] += size

            if v - s >= 0:
                self.pos[i] -= s
            else:
                self.pos[i] = 0
                self.size[i] += abs(v - s)

            if self.size[i] + self.pos[i] > self.image.size[i]:
                self.size[i] = self.image.size[i] - self.pos[i]

        return True

    def crop(self, check_transparent: bool = True):
        container = BytesIO()
        region = self.image.crop(self.crop_positions)
        region.save(container, format='PNG', quality=50)

        if check_transparent:
            transparent = self.transparent_ratio(region)
            if transparent >= self.max_transparent_ratio:
                self.pos = []

                return self.crop()

        return container.getvalue()
