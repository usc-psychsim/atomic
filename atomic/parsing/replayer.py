import itertools
import logging
import os.path
import traceback
from atomic.definitions.map_utils import getSandRMap, getSandRVictims, getSandRCoords, DEFAULT_MAPS
from atomic.inference import set_player_models, DEFAULT_MODELS, DEFAULT_IGNORE
from atomic.parsing.parser import DataParser
from atomic.scenarios.single_player import make_single_player_world
from atomic.model_learning.linear.rewards import create_reward_vector

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

    def get_map(self, parser, logger=logging):
        # Determine which map we're using
        for map_name, map_table in self.maps.items():
            if set(parser.locations) <= map_table['rooms']:
                # This map contains all of the rooms from this log
                return map_name, map_table
            else:
                logger.debug('Map "{}" missing rooms {}'.format(map_name, ','.join(
                    sorted(set(parser.locations) - map_table['rooms']))))

        logger.error('Unable to find matching map for rooms: {}'.format(','.join(sorted(set(parser.locations)))))
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
                result[key] = term[index+1:].split('-')
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
            logger = self.logger.getLogger(os.path.splitext(os.path.basename(fname))[0])
            logger.debug('Full path: {}'.format(fname))
            conditions = self.read_filename(os.path.splitext(os.path.basename(fname))[0])

            # Parse events from log file
            try:
                parser = self.parser_class(fname, logger=logger.getChild(self.parser_class.__name__))
            except:
                logger.error(traceback.format_exc())
                logger.error('Unable to parse log file')
                continue

            try:
                map_name = conditions['CondWin'][0]
                map_table = self.maps[map_name]
            except KeyError:
                # Map not given in filename, try to find fallback
                map_name, map_table = self.get_map(parser, logger)
            if map_name is None or map_table is None:
                continue

            # Create PsychSim model
            logger.info('Creating world with "{}" map'.format(map_name))
            try:
                world, triageAgent, observer, victims, world_map = \
                    make_single_player_world(parser.player_name(), map_table['start'],
                                             map_table['adjacency'], map_table['victims'], False, True,
                                             logger.getChild('makeWorld'))
            except:
                logger.error(traceback.format_exc())
                logger.error('Unable to create world')
                if fname is not None:
                    break
                else:
                    continue
            # Last-minute filling in of models. Would do it earlier if we extracted triageAgent's name
            features = None
            self.model_list = [{dimension: value[index] for index, dimension in enumerate(self.models)}
                               for value in itertools.product(*self.models.values()) if len(value) > 0]
            for index, model in enumerate(self.model_list):
                if 'name' not in model:
                    model['name'] = '{}_{}'.format(triageAgent.name,
                                                   '_'.join([model[dimension] for dimension in self.models]))
                    for dimension in self.models:
                        model[dimension] = self.models[dimension][model[dimension]]
                        if dimension == 'reward':
                            if not isinstance(model[dimension], dict):
                                if features is None:
                                    features = create_reward_vector(triageAgent, world_map.all_locations, world_map.moveActions[triageAgent.name])
                                model[dimension] = {feature: model[dimension][i] for i, feature in enumerate(features)}
            if len(self.model_list) > 0:
                set_player_models(world, observer.name, triageAgent.name, victims, self.model_list)
            # Replay actions from log file
            parser.victimsObj = victims
            try:
                aes, _ = parser.getActionsAndEvents(triageAgent.name, victims, world_map)
            except:
                logger.error(traceback.format_exc())
                logger.error('Unable to extract actions/events')
                continue
            if num_steps == 0:
                last = len(aes)
            else:
                last = num_steps + 1
            self.replay(parser, world, triageAgent, aes, last, logger)
            self.post_replay(parser, world, triageAgent, observer, map_table, victims, world_map)
            world_map.clear()

    def replay(self, parser, world, agent, events, duration, logger):
        try:
            parser.runTimeless(world, agent.name, events, 0, duration, len(events), permissive=True)
        except:
            logger.error(traceback.format_exc())
            logger.error('Unable to complete re-simulation')

    def post_replay(self, parser, world, agent, observer, map_table, victims, world_map):
        pass