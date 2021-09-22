from argparse import ArgumentParser
import configparser
import os.path
import sys
import glob
import traceback
from atomic.definitions.map_utils import get_default_maps
from atomic.parsing.get_psychsim_action_name import Msg2ActionEntry
from atomic.parsing.parse_into_msg_qs import MsgQCreator
from rddl2psychsim.conversion.converter import Converter
try:
    import enlighten
    pbar_manager = enlighten.get_manager()
except ImportError:
    pbar_manager = None

from psychsim.pwl import *
from psychsim.action import *

COND_MAP_TAG = 'CondWin'
COND_TRAIN_TAG = 'CondBtwn'
SUBJECT_ID_TAG = 'Member'
TEAM_ID_TAG = 'Team'
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
        elif os.path.isfile(fname) and fname not in result:
            # We have a lonely single log file (that is not already in the list)
            result.append(fname)
        else:
            # assume this is a file pattern, try to get matches
            result.extend(glob.glob(fname))
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

    def __init__(self, files=[], config=None, maps=None, rddl_file=None, action_file=None, aux_file=None, logger=logging):
        # Extract files to process
        self.files = accumulate_files(files)

        # Extract maps
#        self.maps = get_default_maps(logger) if maps is None else maps

        if isinstance(config, str):
            self.config = configparser.ConfigParser()
            self.config.read(config)
        else:
            self.config = config
        self.logger = logger
        self.rddl_file = rddl_file
        if action_file:
            Msg2ActionEntry.read_psysim_msg_conversion(os.path.join(os.path.dirname(__file__), '..', '..', action_file), os.path.join(os.path.dirname(__file__), '..', '..', aux_file))
            self.msg_types = Msg2ActionEntry.get_msg_types()
        else:
            self.msg_types = None
        self.derived_features = []
        self.times = {}

        # information for each log file # TODO maybe encapsulate in an object and send as arg in post_replay()?
        self.triage_agent = None
        self.observer = None

        self.pbar = None

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
            self.process_file(fname, config, num_steps)
        self.finish()

    def process_file(self, fname, config, num_steps):
        logger = self.logger.getLogger(os.path.splitext(os.path.basename(fname))[0])
        logger.debug('Full path: {}'.format(fname))

        # Parse events from log file
        logger_name = self.__class__.__name__
        try:
            parser = MsgQCreator(fname, logger=logger.getChild(logger_name))
        except:
            logger.error('Unable to parse gamelog messages')
            logger.error(traceback.format_exc())
            return False

        rddl_converter = self.pre_replay(parser, config, logger=logger.getChild('pre_replay'))

        if rddl_converter:
            # Replay actions from log file
            try:
                parser.getActionsAndEvents(None, None)
            except:
                logger.error(traceback.format_exc())
                logger.error('Unable to extract actions/events')
                return False
            if num_steps == 0:
                last = len(parser.actions)
            else:
                last = num_steps + 1
            try:
                self.replay(parser, rddl_converter, last, logger)
                logger.info(f'Re-simulation successfully processed all {self.times[fname]} messages')
            except:
                logger.error(traceback.format_exc())
                logger.error(f'Re-simulation exited on message {self.times[fname]}')
            if self.pbar:
                self.pbar.close()
        self.post_replay(parser, logger)
        return True

    def pre_replay(self, parser, config=None, logger=logging):
        fname = parser.jsonFile
        # Create PsychSim model
        logger.debug('Creating world')

        try:
            parser.startProcessing(self.derived_features, self.msg_types)
        except:
            logger.error('Unable to start parser')
            logger.error(traceback.format_exc())
            return None

        try:
            if self.rddl_file:
                # Team mission
                rddl_converter = Converter()
                rddl_converter.convert_file(self.rddl_file, verbose=False)

                victim_counts = {}
                for victim in parser.jsonParser.victims:
                    if victim.room not in victim_counts:
                        for player_name in rddl_converter.world.agents:
                            var = rddl_converter.world.defineState(player_name, f'(visited, {victim.room})', bool)
                            rddl_converter.world.setFeature(var, rddl_converter.world.getState(player_name, 'pLoc', unique=True) == victim.room)
                            tree = makeTree({'if': falseRow(var) & equalRow(stateKey(player_name, 'pLoc', True), victim.room),
                                True: setTrueMatrix(var), False: noChangeMatrix(var)})
                            rddl_converter.world.setDynamics(var, True, tree)
                        victim_counts[victim.room] = {}
                    victim_counts[victim.room][victim.color] = victim_counts[victim.room].get(victim.color, 0)+1
                # Load in true victim counts
                for var in sorted(rddl_converter.world.variables):
                    if var[:37] == '__WORLD__\'s (vcounter_unsaved_regular':
                        room = var[39:-1]
                        value = 'regular'
                        if room not in victim_counts:
                            rddl_converter.world.setFeature(var, 0)
                        elif value not in victim_counts[room]:
                            rddl_converter.world.setFeature(var, 0)
                        else:
                            rddl_converter.world.setFeature(var, victim_counts[room][value])
                    elif var[:38] == '__WORLD__\'s (vcounter_unsaved_critical':
                        room = var[40:-1]
                        value = 'critical'
                        if room not in victim_counts:
                            rddl_converter.world.setFeature(var, 0)
                        elif value not in victim_counts[room]:
                            rddl_converter.world.setFeature(var, 0)
                        else:
                            rddl_converter.world.setFeature(var, victim_counts[room][value])

                players = set(parser.agentToPlayer.keys())
                zero_models = {name: rddl_converter.world.agents[name].zero_level() for name in players}
                for name in players:
                    agent = rddl_converter.world.agents[name]
#                    agent.setAttribute('static', True, agent.get_true_model())
#                    agent.create_belief_state()
                    agent.setAttribute('selection', 'distribution', zero_models[name])
#                    agent.set_observations()
#                for name in players:
#                    for other_name in players-{name}:
#                        other_agent = rddl_converter.world.agents[other_name]
#                        rddl_converter.world.setModel(name, zero_models[name], other_name, other_agent.get_true_model())

            else:
                # Not creating PsychSim model
                return None
        except:
            logger.error('Unable to create world')
            exc_type, exc_value, exc_traceback = sys.exc_info()
            logger.error(traceback.format_exc())
            return None
        return rddl_converter

    def replay(self, parser, rddl_converter, duration, logger):
        world = rddl_converter.world
        num = len(parser.actions)
        old_rooms = {}
        new_rooms = {}
        global pbar_manager
        if pbar_manager:
            self.pbar = pbar_manager.counter(total=len(parser.actions), unit='steps', leave=False)
        else:
            pbar = None
        prefix = stateKey(WORLD, '(vcounter_')
        old_count = {var: world.getFeature(var, unique=True) for var in world.variables if var[:len(prefix)] == prefix}
        for var, count in sorted(old_count.items()):
            if count != 0:
                logging.info(f'Nonzero victim count {var[len(prefix):-1]}: {count}')
        for i, msgs in enumerate(parser.actions):
            if self.pbar: self.pbar.update()
            self.times[parser.jsonFile] = i
            if i > duration:
                break
            assert len(world.state) == 1
            old_rooms.clear()
            new_rooms.clear()
            logger.info(f'Message {i} out of {num}')
            debug = {ag_name: {'preserve_states': True} for ag_name in rddl_converter.actions}
            
            actions = {}
            any_none = False
            for player_name, msg in msgs.items():
                if msg['sub_type'] == 'Event:location' and msg['old_room_name'] == '':
                    logger.warning(f'Empty room in message {i} {msg} for player {player_name}')
                    world.setState(player_name, 'pLoc', msg['room_name'], recurse=True)
                    msg['sub_type'] = 'noop'
            for player_name, msg in msgs.items():
                logging.info(msg)
                try:
                    action_name = Msg2ActionEntry.get_action(msg)
                except KeyError:
                    logger.error(f'Unable to extract action from {msg}')
                    del msg['room_name']
                    action_name = None
                if action_name in rddl_converter.actions[player_name]:
                    logger.info(f'Msg {msg} becomes {action_name}')
                else:
                    logger.warning(f'Msg {i} {msg} has unknown action {action_name}')
                    if msg['sub_type'] == 'Event:location':
                        logger.warning(f'Unable to find message {i} move action for {player_name} from {msg["old_room_name"]} to {msg["room_name"]}')
                    action_name = Msg2ActionEntry.get_action({'playername':player_name, 'sub_type':'noop'})
                action = rddl_converter.actions[player_name][action_name]
                if action not in world.agents[player_name].getLegalActions():
                    illegal = True # Maybe we can salvage something and flip this flag
                    verb_elements = action['verb'].split('_')
                    if verb_elements[0] == 'pickup':
                        loc = world.getState(player_name, 'pLoc', unique=True)
                        unsaved = world.getState(WORLD, f'(vcounter_unsaved_{verb_elements[2]}, {loc})', unique=True)
                        saved = world.getState(WORLD, f'(vcounter_saved_{verb_elements[2]}, {loc})', unique=True)
                        if unsaved == 0 and saved > 0:
                            logger.warning(f'No unsaved {verb_elements[2]} victims for {action}.')
                            verb = action['verb'].replace('unsaved', 'saved')
                            action = ActionSet([Action({'subject': action['subject'], 'verb': verb})])
                            logger.warning('There are {saved} saved ones, so changing to {action}.')
                            illegal = False
                        else:
                            logger.error(f'No saved or unsaved {verb_elements[2]} victims in {loc}')
                    elif action['verb'][:6] in {'pickup', 'triage'}:
                        loc = world.getState(player_name, 'pLoc', unique=True)
                        logger.error(f'{player_name}\'s pLoc = {loc}')
                        logger.error(f'{player_name}\'s role = {world.getState(player_name, "pRole", unique=True)}')
                        var = stateKey(WORLD, f'(vcounter_unsaved_{action["verb"][7:]}, {loc})')
                        logger.error(f'{var} = {world.getFeature(var, unique=True)}')
                    else:
                        tree = world.agents[player_name].legal[action]
                        for var in sorted(tree.getKeysIn()):
                            logger.error(f'{var} = {world.getFeature(var, unique=True)}')
                    if illegal:
                        raise ValueError(f'Action {action} in msg {i} is currently illegal')
                actions[player_name] = action
                if 'old_room_name' in msg and msg['old_room_name']:
                    old_rooms[player_name] = msg['old_room_name']
                if 'room_name' in msg and action['verb'] != 'noop':
                    new_rooms[player_name] = msg['room_name']
            for name, models in world.get_current_models().items():
                if name in old_rooms and old_rooms[name] != world.getState(name, 'pLoc', unique=True):
                    raise ValueError(f'Before message {i}, {name} is in {world.getState(name, "pLoc", unique=True)}, not {old_rooms[name]}')
                for model in models:
                    beliefs = world.agents[name].getAttribute('beliefs', model)
                    if beliefs is not True:
                        for player_name, room in old_rooms.items():
                            if room and world.getState(player_name, 'pLoc', beliefs, True) != room:
                                raise ValueError(f'Before message {i}, {model} believes {player_name} to be in {world.getState(player_name, "pLoc", beliefs, True)}, not {room}')
            self.pre_step()
            logger.info(f'Actions: {", ".join(sorted(map(str, actions.values())))}')
            world.step(actions, debug=debug)
            if len(actions) < len(parser.agentToPlayer):
                logger.error(f'Missing action in msg {i} for {sorted(parser.agentToPlayer.keys()-actions.keys())}')
                break
            player = world.agents['p3']
            logger.info(f'Completed step for message {i} (R={player.reward(model=player.get_true_model())})')
            self.post_step(actions, debug, logger)
            for name, models in world.get_current_models().items():
                if name in new_rooms and new_rooms[name] != world.getState(name, 'pLoc', unique=True):
                    raise ValueError(f'After message {i}, {name} is in {world.getState(name, "pLoc", unique=True)}, not {new_rooms[name]}')
                else:
                    logger.debug(f'After message {i}, {name} is in correct location {world.getState(name, "pLoc", unique=True)}')
                var = stateKey(name, f'(visited, {world.getState(name, "pLoc", unique=True)})')
                if var in world.variables:
                    if not world.getFeature(var, unique=True):
                        logger.warning(f'After message {i}, {name} has not recorded visitation of {world.getState(name, "pLoc", unique=True)}')
                        raise RuntimeError
                    else:
                        logger.debug(f'After message {i}, {name} has correctly recorded visitation of {world.getState(name, "pLoc", unique=True)}')
                for model in models:
                    beliefs = world.agents[name].getAttribute('beliefs', model)
                    if beliefs is not True:
                        for player_name, room in new_rooms.items():
                            if world.getState(player_name, 'pLoc', beliefs, True) != room:
                                    raise ValueError(f'After message {i}, {model} believes {player_name} to be in {world.getState(player_name, "pLoc", beliefs, True)}, not {room}')
            # Look for count changes
            for var, count in sorted(old_count.items()):
                new_count = world.getFeature(var, unique=True)
                if new_count != count:
                    logging.info(f'Victim count change for {var[len(prefix):-1]}: {count} -> {new_count}')
                    old_count[var] = new_count

    def post_replay(self, parser, logger=logging):
        pass

    def pre_step(self, logger=logging):
        pass

    def post_step(self, actions, debug, logger=logging):
        pass

    def finish(self):
        pass

    def parameterized_replay(self, args):
        if args['profile']:
            return cProfile.run('self.process_files(args["number"])', sort=1)
        elif args['1']:
            return self.process_files(args['number'], args['config'], replayer.files[0])
        else:
            return self.process_files(args['number'], args['config'])

def parse_replay_config(fname, parser):
    """
    Extracts command-line arguments from an INI file (first argument)
    """
    config = configparser.ConfigParser()
    config.read(fname)
    args = {}
    language = config.get('domain', 'language', fallback='RDDL')
    if language == 'RDDL':
        root = os.path.join(os.path.dirname(__file__), '..', '..')
        mapping = {'rddl': ('domain', 'filename'), 'actions': ('domain', 'actions'), 'aux': ('domain', 'aux'),
            'debug': ('run', 'debug'), 'profile': ('run', 'profile'), 'number': ('run', 'steps')}
        for flag, entry in mapping.items():
            default = parser.get_default(flag)
            if isinstance(default, bool):
                args[flag] = config.getboolean(entry[0], entry[1], fallback=default)
            elif isinstance(default, int):
                args[flag] = config.getint(entry[0], entry[1], fallback=default)
            else:
                args[flag] = config.get(entry[0], entry[1], fallback=None)
                if flag in {'rddl', 'actions', 'aux'}:
                    args[flag] = os.path.join(root, args[flag])
    elif language == 'none':
        pass
    else:
        raise ValueError(f'Unknown domain language: {language}')        
    return args

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

if __name__ == '__main__':
    # Process command-line arguments
    args = parse_replay_args(replay_parser())
    replayer = Replayer(args['fname'], args['config'], None, args['rddl'], args['actions'], args['aux'], logging)
    replayer.parameterized_replay(args)
