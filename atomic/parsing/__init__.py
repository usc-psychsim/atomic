import logging
from atomic.definitions.victims import Victims
from atomic.definitions.world_map import WorldMap


class GameLogParser(object):
    """
    Represents a game's log file parser for PsychSim modeling.
    """

    def __init__(self, filename, processor=None, logger=logging):
        """
        Creates a new log file parser.
        :param str filename: the name of the file to be parsed.
        :param ParsingProcessor processor: the parsing processor, for pre- and post-step processing.
        :param logger: the logger handler.
        """
        self.filename = filename
        self.processor = processor
        self.logger = logger

    def getActionsAndEvents(self, victims, world_map, maxEvents=-1):
        """
        Gets actions and events from this parser's log for the given agent.
        :param Victims victims: the distribution of victims over the world.
        :param WorldMap world_map: the world map with all locations.
        :param int maxEvents: the maximum number of events to be parsed.
        :return:
        """
        pass

    def runTimeless(self, world, start, end, ffwdTo=0, prune_threshold=None, permissive=False):
        """
        Run actions and flag resetting events in the order they're given. No notion of timestamps
        """
        pass


class ParsingProcessor(object):
    """
    Utility class to process parsing (pre- and post-parse step functions)
    """

    def __init__(self):
        self.parser = None

    def pre_step(self, world):
        pass

    def post_step(self, world, act):
        pass
