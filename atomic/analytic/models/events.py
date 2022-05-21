from enum import Enum, auto


class JagEvent(Enum):
    DISCOVERED = auto()
    AWARENESS = auto()
    PREPARING = auto()
    ADDRESSING = auto()
    COMPLETION = auto()
    SUMMARY = auto()

    def __lt__(self, other):
        """
        USC
        """
        if self.__class__ is other.__class__:
            return self.value < other.value
        return NotImplemented
