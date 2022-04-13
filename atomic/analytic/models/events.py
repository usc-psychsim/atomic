from enum import Enum, auto


class JagEvent(Enum):
    DISCOVERED = auto()
    AWARENESS = auto()
    PREPARING = auto()
    ADDRESSING = auto()
    COMPLETION = auto()
    SUMMARY = auto()
