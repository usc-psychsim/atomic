import itertools
import logging
import os.path
import traceback
from atomic.definitions.map_utils import get_default_maps
from atomic.inference import set_player_models, DEFAULT_MODELS, DEFAULT_IGNORE
from atomic.parsing import ParsingProcessor
from atomic.parsing.csv_parser import ProcessCSV
from atomic.parsing.message_processing import ProcessParsedJson
from atomic.scenarios.single_player import make_single_player_world

COND_MAP_TAG = 'CondWin'
COND_TRAIN_TAG = 'CondBtwn'
SUBJECT_ID_TAG = 'Member'
TRIAL_TAG = 'Trial'


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
    :ivar files: List of names of the log files to process
    :type files: List(str)
    """

    def __init__(self, files=[], maps=None, models=None, ignore_models=None, create_observer=True,
                 processor=None, logger=logging):
        # Extract files to process
        self.files = accumulate_files(files)
        self.create_observer = create_observer
        self.processor = processor
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
        self.maps = get_default_maps(logger) if maps is None else maps

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

        # todo to be retro-compatible would have to determine the map some other way..
        logger.error('Unable to find matching map')
        return None, None

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
            self.conditions = filename_to_condition(os.path.splitext(os.path.basename(fname))[0])

            map_name, self.map_table = self.get_map(logger)
            if map_name is None or self.map_table is None:
                # could not determine map
                continue

            # Parse events from log file
            logger_name = type(self.processor).__name__ if self.processor is not None else ''
            _, ext = os.path.splitext(fname)
            ext = ext.lower()
            if ext == '.csv' or ext == '.xlsx':
                self.parser = ProcessCSV(fname, self.processor, logger.getChild(logger_name))
            elif ext == '.metadata':
                self.parser = ProcessParsedJson(
                    fname, self.map_table, self.processor, logger.getChild(logger_name))
            else:
                raise ValueError('Unable to parse log file: {}, unknown extension.'.format(fname))

            # set parser to processor
            if self.processor is not None:
                self.processor.parser = self.parser

            if not self.pre_replay(logger=logger.getChild('pre_replay')):
                # Failure in creating world
                continue

            # Replay actions from log file
            try:
                self.parser.getActionsAndEvents(self.victims, self.world_map)
            except:
                logger.error(traceback.format_exc())
                logger.error('Unable to extract actions/events')
                continue
            if num_steps == 0:
                last = len(self.parser.actions)
            else:
                last = num_steps + 1
            self.replay(last, logger)
            self.post_replay()
            self.world_map.clear()

    def pre_replay(self, logger=logging):
        # Create PsychSim model
        logger.info('Creating world with "{}" map'.format(self.map_table.name))
        self.parser.startProcessing([])
        try:
            self.world, self.triage_agent, self.observer, self.victims, self.world_map = \
                make_single_player_world(self.parser.player_name(), self.map_table.init_loc,
                                         self.map_table.adjacency, self.map_table.victims, False, True,
                                         self.create_observer, logger.getChild('make_single_player_world'))
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
        #        self.parser.victimsObj = self.victims
        return True

    def replay(self, duration, logger):
        try:
            self.parser.runTimeless(self.world, 0, duration, duration, permissive=True)
        except:
            logger.error(traceback.format_exc())
            logger.error('Unable to complete re-simulation')

    def post_replay(self):
        pass

    def read_filename(self, fname):
        raise DeprecationWarning('Use filename_to_condition function (in this module) instead')


def filename_to_condition(fname):
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


def find_trial(trial, log_dir):
    """
    :return: the filename in the given log directory for the given trial
    """
    for fname in os.listdir(log_dir):
        if int(filename_to_condition(os.path.join(log_dir, fname))['Trial']) == trial:
            return fname
    else:
        raise ValueError('Unable to find a file for log {} in {}'.format(trial, log_dir))
