from enum import IntEnum


class Directions(IntEnum):
    N = 0
    E = 1
    S = 2
    W = 3


GREEN_STR = 'regular'
GOLD_STR = 'critical'
WHITE_STR = 'white'
RED_STR = 'red'
MISSION_DURATION = 60 * 15

COLOR_TRANSLATION = {'Green': 'green', 'Gold': 'yellow'}

## A flag for whether we actually inject psychsim actions when parsing
## or we're just doing a dry run for debugging
INJECT_PSYCH_ACTIONS = False