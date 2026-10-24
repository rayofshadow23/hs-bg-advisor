from pathlib import Path

import yaml

REGIONS_PATH = Path(__file__).with_name("regions.yaml")


def load_regions(path=REGIONS_PATH):
    with open(path) as f:
        return yaml.safe_load(f)


def crop(img, rect):
    x, y, w, h = rect
    return img[y:y + h, x:x + w]
