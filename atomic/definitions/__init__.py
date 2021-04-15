from enum import IntEnum


class Directions(IntEnum):
    N = 0
    E = 1
    S = 2
    W = 3


GREEN_STR = 'green'
GOLD_STR = 'yellow'
WHITE_STR = 'white'
RED_STR = 'red'
MISSION_DURATION = 60 * 15

COLOR_TRANSLATION = {'Green': 'green', 'Gold': 'yellow'}