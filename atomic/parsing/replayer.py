import itertools
import logging
import os.path
import traceback
from atomic.definitions.map_utils import getSandRMap, getSandRVictims, getSandRCoords, DEFAULT_MAPS
from atomic.inference import set_player_models, DEFAULT_MODELS, DEFAULT_IGNORE
from atomic.parsing.parser import DataParser
from atomic.scenarios.single_player import make_single_player_world


def accumulate_files(files):
    """
    Accumulate a list of files from a given list of names of files and directories
    :type files: List(str)
    :rtype: List(str)
    """
    result = []
    for fname in files:
        if os.path.isdir(fname):
            # We have a directory full of log files to process
            result += [os.path.join(fname, name) for name in os.listdir(fname)
                       if os.path.splitext(name)[1] == '.csv' and os.path.join(fname, name) not in result]
        elif fname not in result:
            # We have a lonely single log file (that is not already in the list)
            result.append(fname)
    return result


class Replayer(object):
    """
    Base class for replaying log files
    :cvar parser_class: Class of parser to instantiate for each file (default is DataParser)
    :ivar files: List of names of the log files to process
    :type files: List(str)
    """

    parser_class = DataParser

    def __init__(self, files=[], maps=None, models=None, ignore_models=None, logger=logging):
        # Extract files to process
        self.files = accumulate_files(files)
        self.logger = logger

        # information for each log file # TODO maybe encapsulate in an object and send as arg in post_replay()?
        self.world = None
        self.triage_agent = None
        self.observer = None
        self.victims = None
        self.world_map = None
        self.map_table = None
        self.parser = None
        self.conditions = None
        self.file_name = None

        # Extract maps
        if maps is None:
            maps = DEFAULT_MAPS
        for map_name, map_table in maps.items():
            logger = self.logger.getLogger(map_name)
            map_table['adjacency'] = getSandRMap(fname=map_table['room_file'], logger=logger)
            map_table['rooms'] = set(map_table['adjacency'].keys())
            map_table['victims'] = getSandRVictims(fname=map_table['victim_file'])
            map_table['coordinates'] = getSandRCoords(fname=map_table['coords_file'])
            map_table['start'] = next(iter(map_table['adjacency'].keys()))
            map_table['name'] = map_name
        self.maps = maps

        # Set player models for observer agent
        if models is None:
            models = DEFAULT_MODELS
        if ignore_models is None:
            ignore_models = DEFAULT_IGNORE
        for dimension, entries in models.items():
            if dimension in ignore_models:
                first = True
                for key in list(entries.keys()):
                    if first:
                        first = False
                    else:
                        del entries[key]
        self.model_list = [{dimension: value[index] for index, dimension in enumerate(models)}
                           for value in itertools.product(*models.values()) if len(value) > 0]
        self.models = models

    def get_map(self, logger=logging):
        # try to get map name directly from conditions dictionary
        try:
            map_name = self.conditions['CondWin'][0]
            map_table = self.maps[map_name]
            return map_name, map_table
        except KeyError:
            # Map not given in filename, try to find fallback
            pass

        # Determine which map we're using from the number of rooms
        for map_name, map_table in self.maps.items():
            if set(self.parser.locations) <= map_table['rooms']:
                # This map contains all of the rooms from this log
                return map_name, map_table
            else:
                logger.debug('Map "{}" missing rooms {}'.format(map_name, ','.join(
                    sorted(set(self.parser.locations) - map_table['rooms']))))

        logger.error('Unable to find matching map for rooms: {}'.format(','.join(sorted(set(self.parser.locations)))))
        return None, None

    def read_filename(self, fname):
        """
        Follows the ASIST file naming convention to extract key/value pairs out of the given filename
        """
        elements = fname.split('_')
        result = {}
        for term in elements:
            try:
                index = term.index('-')
                key = term[:index]
                result[key] = term[index + 1:].split('-')
                if len(result[key]) == 1:
                    result[key] = result[key][0]
            except ValueError:
                continue
        return result

    def process_files(self, num_steps=0, fname=None):
        """
        :param num_steps: if nonzero, the maximum number of steps to replay from each log (default is 0)
        :type num_steps: int
        :param fname: Name of log file to process (default is all of them)
        :type fname: str
        """
        if fname is None:
            files = self.files
        else:
            files = [fname]
        # Get to work
        for fname in files:
            self.file_name = fname
            logger = self.logger.getLogger(os.path.splitext(os.path.basename(fname))[0])
            logger.debug('Full path: {}'.format(fname))
            self.conditions = self.read_filename(os.path.splitext(os.path.basename(fname))[0])

            # Parse events from log file
            try:
                self.parser = self.parser_class(fname, logger=logger.getChild(self.parser_class.__name__))
            except:
                logger.error(traceback.format_exc())
                logger.error('Unable to parse log file')
                continue

            map_name, self.map_table = self.get_map(logger)
            if map_name is None or self.map_table is None:
                continue

            if not self.pre_replay(map_name, logger=logger.getChild('pre_replay')):
                # Failure in creating world
                continue

            # Replay actions from log file
            try:
                aes, _ = self.parser.getActionsAndEvents(self.triage_agent.name, self.victims, self.world_map)
            except:
                logger.error(traceback.format_exc())
                logger.error('Unable to extract actions/events')
                continue
            if num_steps == 0:
                last = len(aes)
            else:
                last = num_steps + 1
            self.replay(aes, last, logger)
            self.post_replay()
            self.world_map.clear()

    def pre_replay(self, map_name, logger=logging):
        # Create PsychSim model
        logger.info('Creating world with "{}" map'.format(map_name))
        try:
            self.world, self.triage_agent, self.observer, self.victims, self.world_map = \
                make_single_player_world(self.parser.player_name(), self.map_table['start'],
                                         self.map_table['adjacency'], self.map_table['victims'], False, True, {},
                                         logger.getChild('make_single_player_world'))
        except:
            logger.error(traceback.format_exc())
            logger.error('Unable to create world')
            return False
        # Last-minute filling in of models. Would do it earlier if we extracted triage_agent's name
        features = None
        self.model_list = [{dimension: value[index] for index, dimension in enumerate(self.models)}
                           for value in itertools.product(*self.models.values()) if len(value) > 0]
        for index, model in enumerate(self.model_list):
            if 'name' not in model:
                model['name'] = '{}_{}'.format(self.triage_agent.name,
                                               '_'.join([model[dimension] for dimension in self.models]))
                for dimension in self.models:
                    model[dimension] = self.models[dimension][model[dimension]]
                    if dimension == 'reward':
                        if not isinstance(model[dimension], dict):
                            if features is None:
                                import atomic.model_learning.linear.rewards as rewards
                                features = rewards.create_reward_vector(
                                    self.triage_agent, self.world_map.all_locations,
                                    self.world_map.moveActions[self.triage_agent.name])
                            model[dimension] = {feature: model[dimension][i] for i, feature in enumerate(features)}
        if len(self.model_list) > 0:
            set_player_models(self.world, self.observer.name, self.triage_agent.name, self.victims, self.model_list)
        self.parser.victimsObj = self.victims
        return True

    def replay(self, events, duration, logger):
        try:
            self.parser.runTimeless(self.world, self.triage_agent.name, events, 0, duration, len(events),
                                    permissive=True)
        except:
            logger.error(traceback.format_exc())
            logger.error('Unable to complete re-simulation')

    def post_replay(self):
        pass
