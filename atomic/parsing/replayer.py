from argparse import ArgumentParser
import configparser
import cProfile
import json
import logging
import os.path
import sys
import glob
import traceback
try:
    import enlighten
    pbar_manager = enlighten.get_manager()
except ImportError:
    pbar_manager = None

from atomic.parsing.asist_world import ASISTWorld

COND_MAP_TAG = 'CondWin'
COND_TRAIN_TAG = 'CondBtwn'
SUBJECT_ID_TAG = 'Member'
TEAM_ID_TAG = 'Team'
TRIAL_TAG = 'Trial'


def accumulate_files(files, include_trials=None, ext='.metadata', logger=logging):
    """
    Accumulate a list of files from a given list of names of files and directories
    :type files: List(str)
    :rtype: List(str)
    :type include_trials: Set/List(int)
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
        conditions = filename_to_condition(os.path.splitext(os.path.basename(fname))[0])
        try:
            trial = conditions['Trial']
        except KeyError:
            try:
                trial = conditions['TrialPlanning']
            except KeyError:
                logger.warning(f'Unable to identify trial corresponding to {os.path.basename(fname)}')
                continue
        if trial == 'Competency':
            logging.warning(f'Ignoring competency trial {os.path.basename(trial)}')
        elif trial == 'Training':
            logging.warning(f'Ignoring training trial {os.path.basename(trial)}')
        elif include_trials is None or int(trial[1:]) in include_trials:
            trials[trial] = trials.get(trial, []) + [fname]
    for trial, files in trials.items():
        files.sort(key=lambda fname: int(filename_to_condition(os.path.splitext(os.path.basename(fname))[0])['Vers']))
        if len(files) > 1:
            logging.warning(f'Ignoring version(s) of trial {os.path.basename(trial)} '
                            f'{", ".join([filename_to_condition(os.path.splitext(fname)[0])["Vers"] for fname in files[:-1]])} '
                            f'in favor of version {filename_to_condition(os.path.splitext(files[-1])[0])["Vers"]}')
    result = [files[-1] for files in trials.values()]
    return result


class Replayer(object):
    """
    Base class for replaying log files
    :ivar files: List of names of the log files to process
    :type files: List(str)
    """

    def __init__(self, files=[], trials=None, config=None, logger=logging):
        # Extract files to process
        self.files = accumulate_files(files, trials)

        if isinstance(config, str):
            self.config = configparser.ConfigParser()
            self.config.read(config)
        else:
            self.config = config
        self.logger = logger

        # Per-file PsychSim objects
        self.worlds = {}
        self.sources = set()

        self.pbar = None

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
            self.process_file(fname, num_steps)
        self.finish()

    def process_file(self, fname, num_steps):
        self.logger.debug(f'Processing file {fname}')

        self.pre_replay(fname)
        self.replay(fname, num_steps)
        self.post_replay(fname)

    def pre_replay(self, fname):
        logger_child = self.logger.getLogger(os.path.splitext(os.path.basename(fname))[0])
        self.worlds[fname] = ASISTWorld(config=self.config, logger=logger_child)
            
    def replay(self, fname, duration):
        global pbar_manager
        num_lines = sum(1 for i in open(fname, 'rb'))
        if pbar_manager:
            try:
                self.pbar = pbar_manager.counter(total=num_lines, unit='steps',
                                                 leave=False)
            except ValueError:
                # Probably not running in a terminal
                self.pbar = None
        else:
            self.pbar = None
        with open(fname, 'rt') as json_file:
            for line_no, line in enumerate(json_file):
                if self.pbar: 
                    self.pbar.update()
                try:
                    msg = json.loads(line)
                except Exception:
                    self.logger.error(traceback.format_exc())
                    self.logger.error(f'Error in reading line {line_no} of {fname}')
                    msg = None
                if msg:
                    self.sources.add(msg['msg']['source'])
                    self.worlds[fname].process_msg(msg)

    def post_replay(self, fname):
        self.worlds[fname].close()

    def pre_step(self, world):
        pass

    def post_step(self, world, actions, t, parser, debug):
        pass

    def finish(self):
        print(sorted(self.sources))
        pass

    def parameterized_replay(self, args, simulate=False):
        if args['profile']:
            return cProfile.runctx('self.process_files(args["number"])', {'self': self, 'args': args}, {}, sort=1)
        elif args['1']:
            return self.process_files(args['number'], replayer.files[0])
        else:
            return self.process_files(args['number'])


def filename_to_condition(fname):
    """
    Follows the ASIST file naming convention to extract key/value pairs out of the given filename
    """
    fname = os.path.splitext(os.path.basename(fname))[0]
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
        raise ValueError(f'Unable to find a file for log {trial} in {log_dir}')


def replay_parser():
    parser = ArgumentParser()
    parser.add_argument('--config', help='Config file specifying execution parameters')
    parser.add_argument('fname', nargs='+',
                        help='Log file(s) (or directory of log files) to process')
    parser.add_argument('-1', '--1', action='store_true', help='Exit after the first run-through')
    parser.add_argument('-n', '--number', type=int, default=0,
                        help='Number of steps to replay (default is 0, meaning all)')
    parser.add_argument('-t', '--trials', type=int, nargs='*',
                        help='Trials to include (default is all)')
    parser.add_argument('-d', '--debug', default='WARNING', help='Level of logging detail')
    parser.add_argument('--profile', action='store_true', help='Run profiler')
    return parser


def parse_replay_args(parser, arg_list=None):
    args = vars(parser.parse_args(args=arg_list))
    # Extract logging level from command-line argument
    level = getattr(logging, args['debug'].upper(), None)
    if not isinstance(level, int):
        raise ValueError('Invalid debug level: {}'.format(args['debug']))
    logging.basicConfig(level=level)
    if isinstance(args['trials'], list):
        args['trials'] = set(args['trials'])
    return args


if __name__ == '__main__':
    # Process command-line arguments
    args = parse_replay_args(replay_parser())
    replayer = Replayer(args['fname'], args['trials'], args['config'], logging)
    replayer.parameterized_replay(args)
