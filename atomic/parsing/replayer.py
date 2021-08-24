from argparse import ArgumentParser
import configparser
import copy
import csv
import itertools
import logging
import os.path
import sys
import traceback
from atomic.definitions.map_utils import get_default_maps
from atomic.parsing.get_psychsim_action_name import Msg2ActionEntry
from atomic.parsing.csv_parser import ProcessCSV
from atomic.parsing.parse_into_msg_qs import MsgQCreator
from atomic.scenarios.single_player import make_single_player_world
from atomic.bin.cluster_features import _get_feature_values, _get_derived_features
from rddl2psychsim.conversion.converter import Converter

from psychsim.pwl import *

COND_MAP_TAG = 'CondWin'
COND_TRAIN_TAG = 'CondBtwn'
SUBJECT_ID_TAG = 'Member'
TRIAL_TAG = 'Trial'


def accumulate_files(files, ext='.metadata'):
    """
    Accumulate a list of files from a given list of names of files and directories
    :type files: List(str)
    :rtype: List(str)
    """
    result = []
    for fname in files:
        if os.path.isdir(fname):
            # We have a directory full of log files to process
            result += [os.path.join(fname, name) for name in sorted(os.listdir(fname))
                       if os.path.splitext(name)[1] == ext and os.path.join(fname, name) not in result]
        elif fname not in result:
            # We have a lonely single log file (that is not already in the list)
            result.append(fname)
    # Look for alternate versions of the same trial and use only the most recent
    trials = {}
    for fname in result:
        trial = fname[:fname.find('Vers')]
        trials[trial] = trials.get(trial, []) + [fname]
    for trial, files in trials.items():
        files.sort(key=lambda fname: filename_to_condition(fname)['Vers'])
        if len(files) > 1:
            logging.warning(f'Ignoring version(s) of trial {os.path.basename(trial)} {", ".join([filename_to_condition(fname)["Vers"] for fname in files[:-1]])} '\
                f'in favor of version {filename_to_condition(files[-1])["Vers"]}')
    result = [files[-1] for files in trials.values()]
    return result


class Replayer(object):
    """
    Base class for replaying log files
    :ivar files: List of names of the log files to process
    :type files: List(str)
    :ivar rddl_file: Name of file containing the RDDL specification of the domain
    :type rddl_file: str
    :ivar action_file: Name of CSV file containing the mapping between JSON messages and PsychSim actions
    :type action_file: str
    """
    OBSERVER = 'ATOMIC'

    def __init__(self, files=[], maps=None, processor=None, rddl_file=None, action_file=None, feature_output=None, aux_file=None, logger=logging):
        # Extract files to process
        self.files = accumulate_files(files)
        self.processor = processor
        self.logger = logger
        self.rddl_file = rddl_file
        if action_file:
            Msg2ActionEntry.read_psysim_msg_conversion(action_file, aux_file)
            self.msg_types = Msg2ActionEntry.get_msg_types()
        else:
            self.msg_types = None
        self.rddl_converter = None

        # Feature count bookkeeping
        self.derived_features = []
        self.feature_output = feature_output
        self.feature_data = []
        self.condition_fields = None

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

    def get_map(self, logger=logging):
        # try to get map name directly from conditions dictionary
        try:
            map_name = self.conditions['CondWin']
            map_table = self.maps[map_name]
            return map_name, map_table
        except KeyError:
            # Maybe Phase 1 filename scheme?
            map_name = self.conditions['CondWin'][0]
            map_table = self.maps[map_name]
            return map_name, map_table

        # todo to be retro-compatible would have to determine the map some other way..
        logger.error('Unable to find matching map')
        return None, None

    def process_files(self, num_steps=0, config=None, fname=None):
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

            # Parse events from log file
            logger_name = type(self.processor).__name__ if self.processor is not None else ''
            _, ext = os.path.splitext(fname)
            ext = ext.lower()
            if ext == '.csv' or ext == '.xlsx':
                map_name, self.map_table = self.get_map(logger)
                if map_name is None or self.map_table is None:
                    # could not determine map
                    continue
                self.parser = ProcessCSV(fname, self.processor, logger.getChild(logger_name))
            elif ext == '.metadata':
                try:
                    self.parser = MsgQCreator(fname, self.processor, logger=logger.getChild(logger_name))
                except:
                    logger.error('Unable to extract actions/events')
                    logger.error(traceback.format_exc())
                    continue
                self.derived_features = _get_derived_features(self.parser)
            else:
                raise ValueError('Unable to parse log file: {}, unknown extension.'.format(fname))

            # set parser to processor
            if self.processor is not None:
                self.processor.parser = self.parser

            if not self.pre_replay(config, logger=logger.getChild('pre_replay')):
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
            try:
                self.replay(last, logger)
            except:
                logger.error(traceback.format_exc())
                logger.error(f'Re-simulation exited on message {self.t}')
            self.post_replay()
            if self.world_map: self.world_map.clear()
        if self.feature_output:
            assert self.condition_fields is not None, 'Never extracted condition fields from filename'
            with open(self.feature_output, 'w') as csvfile:
                cumulative_fields = [set(row.keys()) for row in self.feature_data]
                fields = self.condition_fields + sorted(set.union(*cumulative_fields)-{'File'})
                fields.append('File')
                writer = csv.DictWriter(csvfile, fields, extrasaction='ignore')
                writer.writeheader()
                for row in self.feature_data:
                    row.update(filename_to_condition(row['File']))
                    writer.writerow(row)

    def pre_replay(self, config=None, logger=logging):
        # Create PsychSim model
        logger.debug('Creating world')

        try:
            self.parser.startProcessing(self.derived_features, self.msg_types)
        except:
            logger.error('Unable to start parser')
            logger.error(traceback.format_exc())
            return False

        if self.feature_output:
            # processes data to extract features depending on type of count
            features = {'File': os.path.splitext(os.path.basename(self.file_name))[0]}
            if self.condition_fields is None:
                self.condition_fields = list(filename_to_condition(features['File']).keys())
            for feature in self.derived_features:
                features.update(_get_feature_values(feature))
            self.feature_data.append(features)

        try:
            if self.rddl_file:
                # Team mission
                self.rddl_converter = Converter()
                self.rddl_converter.convert_file(self.rddl_file)
                self.world = self.rddl_converter.world

                counts = {}
                for victim in self.parser.jsonParser.victims:
                    if victim.room not in counts:
                        counts[victim.room] = {}
                    counts[victim.room][victim.color] = counts[victim.room].get(victim.color, 0)+1
                # Load in true victim counts
                for var in sorted(self.world.variables):
                    if var[:37] == '__WORLD__\'s (vcounter_unsaved_regular':
                        room = var[39:-1]
                        value = 'regular'
                        if room not in counts:
                            self.world.setFeature(var, 0)
                        elif value not in counts[room]:
                            self.world.setFeature(var, 0)
                        else:
                            self.world.setFeature(var, counts[room][value])
                    elif var[:38] == '__WORLD__\'s (vcounter_unsaved_critical':
                        room = var[40:-1]
                        value = 'critical'
                        if room not in counts:
                            self.world.setFeature(var, 0)
                        elif value not in counts[room]:
                            self.world.setFeature(var, 0)
                        else:
                            self.world.setFeature(var, counts[room][value])

                players = set(self.parser.agentToPlayer.keys())
                zero_models = {name: self.world.agents[name].zero_level() for name in players}
                for name in players:
                    agent = self.world.agents[name]
#                    agent.setAttribute('static', True, agent.get_true_model())
#                    agent.create_belief_state()
                    agent.setAttribute('selection', 'distribution', zero_models[name])
#                    agent.set_observations()
#                for name in players:
#                    for other_name in players-{name}:
#                        other_agent = self.world.agents[other_name]
#                        self.world.setModel(name, zero_models[name], other_name, other_agent.get_true_model())

            elif self.feature_output is None:
                # Solo mission
                self.world, self.triage_agent, _, self.victims, self.world_map = \
                    make_single_player_world(self.parser.player_name(), self.map_table.init_loc,
                                             self.map_table.adjacency, self.map_table.victims, False, True,
                                             False, logger.getChild('make_single_player_world'))
            else:
                # Not creating PsychSim model
                return False
        except:
            logger.error('Unable to create world')
            exc_type, exc_value, exc_traceback = sys.exc_info()
            logger.error(traceback.format_exc())
            return False
        return True

    def replay(self, duration, logger):
        if isinstance(self.parser, MsgQCreator):
            num = len(self.parser.actions)
            old_rooms = {}
            new_rooms = {}
            for i, msgs in enumerate(self.parser.actions):
                self.t = i
                if i > duration:
                    break
                assert len(self.world.state) == 1
                old_rooms.clear()
                new_rooms.clear()
                logger.info(f'Message {i} out of {num}')
                debug = {ag_name: {'preserve_states': True} for ag_name in self.rddl_converter.actions}
                
                actions = {}
                any_none = False
                for player_name, msg in msgs.items():
                    if msg['sub_type'] == 'Event:location' and msg['old_room_name'] == '':
                        logger.warning(f'Empty room in message {i} {msg} for player {player_name}')
                        self.world.setState(player_name, 'pLoc', msg['room_name'], recurse=True)
                        msg['sub_type'] = 'noop'
                        action_name = Msg2ActionEntry.get_action(msg)
                for player_name, msg in msgs.items():
                    action_name = Msg2ActionEntry.get_action(msg)
                    if action_name not in self.rddl_converter.actions[player_name]:
                        if msg['sub_type'] == 'Event:Triage':
                            if msg['triage_state'] != 'SUCCESSFUL':
                                loc = self.world.getState(player_name, 'pLoc', unique=True)
                                count = self.world.getState(WORLD, f'(vcounter_unsaved_{msg["type"].lower()}, {loc})', unique=True)
                                logger.warning(f'Ignoring {msg["triage_state"].lower()} triage by {player_name} of {msg["type"].lower()} victim (out of {count} unsaved in {loc})')
                            else:
                                logger.warning(f'Msg {i} {msg} has unknown action {action_name}')
                        action_name = Msg2ActionEntry.get_action({'playername':player_name, 'sub_type':'noop'})
                    else:
                        logger.info(f'Msg {msg} becomes {action_name}')
                    action = self.rddl_converter.actions[player_name][action_name]
                    actions[player_name] = action
                    if action not in self.world.agents[player_name].getLegalActions():
                        if action['verb'][:6] in {'pickup', 'triage'}:
                            loc = self.world.getState(player_name, 'pLoc', unique=True)
                            logger.error(f'{player_name}\'s pLoc = {loc}')
                            logger.error(f'{player_name}\'s role = {self.world.getState(player_name, "pRole", unique=True)}')
                            var = stateKey(WORLD, f'(vcounter_unsaved_{action["verb"][7:]}, {loc})')
                            logger.error(f'{var} = {self.world.getFeature(var, unique=True)}')
                        else:
                            tree = self.world.agents[player_name].legal[action]
                            for var in sorted(tree.getKeysIn()):
                                logger.error(f'{var} = {self.world.getFeature(var, unique=True)}')
                        raise ValueError(f'Action {action} in msg {i} is currently illegal')
                    if 'old_room_name' in msg and msg['old_room_name']:
                        old_rooms[player_name] = msg['old_room_name']
                    if 'room_name' in msg:
                        new_rooms[player_name] = msg['room_name']
                for name, models in self.world.get_current_models().items():
                    if name in old_rooms and old_rooms[name] != self.world.getState(name, 'pLoc', unique=True):
                        raise ValueError(f'Before message {i}, {name} is in {self.world.getState(name, "pLoc", unique=True)}, not {old_rooms[name]}')
                    for model in models:
                        beliefs = self.world.agents[name].getAttribute('beliefs', model)
                        if beliefs is not True:
                            for player_name, room in old_rooms.items():
                                if room and self.world.getState(player_name, 'pLoc', beliefs, True) != room:
                                    raise ValueError(f'Before message {i}, {model} believes {player_name} to be in {self.world.getState(player_name, "pLoc", beliefs, True)}, not {room}')
                self.pre_step()
                self.world.step(actions, debug=debug)
                if len(actions) < len(self.parser.agentToPlayer):
                    logger.error(f'Missing action in msg {i} for {sorted(self.parser.agentToPlayer.keys()-actions.keys())}')
                    break
                logger.info(f'Saved(el_A)={self.world.getState(WORLD, "(vcounter_saved_regular, el_A)", unique=True)}')
                player = self.world.agents['p3']
                logger.info(f'Completed step for message {i} (R={player.reward(model=player.get_true_model())})')
                self.post_step(actions, debug)
                for name, models in self.world.get_current_models().items():
                    if name in new_rooms and new_rooms[name] != self.world.getState(name, 'pLoc', unique=True):
                        raise ValueError(f'After message {i}, {name} is in {self.world.getState(name, "pLoc", unique=True)}, not {new_rooms[name]}')
                    else:
                        logger.info(f'After message {i}, {name} is in correct location {self.world.getState(name, "pLoc", unique=True)}')
                    for model in models:
                        beliefs = self.world.agents[name].getAttribute('beliefs', model)
                        if beliefs is not True:
                            for player_name, room in new_rooms.items():
                                if self.world.getState(player_name, 'pLoc', beliefs, True) != room:
                                        raise ValueError(f'After message {i}, {model} believes {player_name} to be in {self.world.getState(player_name, "pLoc", beliefs, True)}, not {room}')
        else:
            self.parser.runTimeless(self.world, 0, duration, duration, permissive=True)

    def post_replay(self):
        pass

    def pre_step(self):
        pass

    def post_step(self, actions, debug):
        pass

    def read_filename(self, fname):
        raise DeprecationWarning('Use filename_to_condition function (in this module) instead')

    def parameterized_replay(self, args):
        if args['profile']:
            return cProfile.run('self.process_files(args["number"])', sort=1)
        elif args['1']:
            return self.process_files(args['number'], args['config'], replayer.files[0])
        else:
            return self.process_files(args['number'], args['config'])

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

def replay_parser():
    parser = ArgumentParser()
    parser.add_argument('--config', help='Config file specifying execution parameters')
    parser.add_argument('fname', nargs='+',
                        help='Log file(s) (or directory of log files) to process')
    parser.add_argument('-1', '--1', action='store_true', help='Exit after the first run-through')
    parser.add_argument('-n', '--number', type=int, default=0,
                        help='Number of steps to replay (default is 0, meaning all)')
    parser.add_argument('-d', '--debug', default='WARNING', help='Level of logging detail')
    parser.add_argument('--profile', action='store_true', help='Run profiler')
    parser.add_argument('--rddl', help='Name of RDDL file containing domain specification')
    parser.add_argument('--actions', help='Name of CSV file containing JSON to PsychSim action mapping')
    parser.add_argument('--aux', help='Name of auxiliary CSV file for collapsed map')
    parser.add_argument('--feature_file', help='Destination of feature count output')
    return parser

def parse_replay_args(parser):
    args = vars(parser.parse_args())
    if args['config']:
        args.update(parse_replay_config(args['config'], parser))
    # Extract logging level from command-line argument
    level = getattr(logging, args['debug'].upper(), None)
    if not isinstance(level, int):
        raise ValueError('Invalid debug level: {}'.format(args['debug']))
    logging.basicConfig(level=level)
    return args

def parse_replay_config(fname, parser):
    """
    Extracts command-line arguments from an INI file (first argument)
    """
    config = configparser.ConfigParser()
    config.read(fname)
    if config.get('domain', 'language', fallback='RDDL') != 'RDDL':
        raise ValueError(f'Unknown domain language: {config.get("domain", "language", fallback="RDDL")}')
    root = os.path.join(os.path.dirname(__file__), '..', '..')
    mapping = {'rddl': ('domain', 'filename'), 'actions': ('domain', 'actions'), 'aux': ('domain', 'aux'),
        'debug': ('run', 'debug'), 'profile': ('run', 'profile'), 'number': ('run', 'steps')}
    args = {}
    for flag, entry in mapping.items():
        default = parser.get_default(flag)
        if isinstance(default, bool):
            args[flag] = config.getboolean(entry[0], entry[1], fallback=default)
        elif isinstance(default, int):
            args[flag] = config.getint(entry[0], entry[1], fallback=default)
        else:
            args[flag] = config.get(entry[0], entry[1], fallback=None)
    return args

if __name__ == '__main__':
    # Process command-line arguments
    args = parse_replay_args(replay_parser())
    replayer = Replayer(args['fname'], get_default_maps(logging), None, args['rddl'], args['actions'], args['feature_file'], args['aux'], logging)
    replayer.parameterized_replay(args)
