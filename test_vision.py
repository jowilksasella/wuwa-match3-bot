"""Offline regression: python test_vision.py <frame.png> [...]  prints each parsed board."""
import sys

import cv2
import numpy as np

import vision

for path in sys.argv[1:]:
    g, s = vision.read_board(cv2.imdecode(np.fromfile(path, np.uint8), 1))
    print(path.rsplit("/", 1)[-1])
    print(vision.fmt(g, s))
