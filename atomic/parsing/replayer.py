from argparse import ArgumentParser
import configparser
import cProfile
import json
import logging
import numpy
import os.path
import pandas
import glob
import traceback
try:
    import enlighten
    pbar_manager = enlighten.get_manager()
except ImportError:
    pbar_manager = None
import matplotlib.pyplot as plt    

from atomic.analytic import AC_specs
from atomic.parsing.asist_world import ASISTWorld
from atomic.parsing.transcript import Transcript


COND_MAP_TAG = 'CondWin'
COND_TRAIN_TAG = 'CondBtwn'
SUBJECT_ID_TAG = 'Member'
TEAM_ID_TAG = 'Team'
TRIAL_TAG = 'Trial'


def accumulate_files(files, include_trials=None, ext='.metadata', logger=logging, group_by_team=False, clean=False):
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
    teams = {}
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
            logging.warning(f'Ignoring competency trial {os.path.basename(fname)}')
            if clean:
                os.remove(fname)
        elif trial == 'Training':
            logging.warning(f'Ignoring training trial {os.path.basename(fname)}')
            if clean:
                os.remove(fname)
        elif include_trials is None or int(trial[1:]) in include_trials:
            trials[trial] = trials.get(trial, []) + [fname]
            teams[conditions['Team']] = teams.get(conditions['Team'], set()) | {trial}
    for trial, files in trials.items():
        files.sort(key=lambda fname: int(filename_to_condition(os.path.splitext(os.path.basename(fname))[0])['Vers']))
        if len(files) > 1:
            logging.warning(f'Ignoring version(s) of trial {os.path.basename(trial)} '
                            f'{", ".join([filename_to_condition(os.path.splitext(fname)[0])["Vers"] for fname in files[:-1]])} '
                            f'in favor of version {filename_to_condition(os.path.splitext(files[-1])[0])["Vers"]}')
            if clean:
                for fname in files[:-1]:
                    os.remove(fname)
    if group_by_team:
        # Group newest trials by team
        teams = {team: [trials[trial][-1] for trial in sorted(trial_list)] for team, trial_list in teams.items()}
        result = [trial_list for team, trial_list in sorted(teams.items())]
    else:
        result = [files[-1] for files in trials.values()]
    return result


class Replayer(object):
    """
    Base class for replaying log files
    :ivar files: List of names of the log files to process
    :type files: List(str)
    """

    def __init__(self, files=[], trials=None, config=None, strict=False, clean=False, logger=logging):
        # Extract files to process
        self.files = accumulate_files(files, trials, group_by_team=True, clean=clean)

        if isinstance(config, str):
            self.config = configparser.ConfigParser()
            self.config.read(config)
        else:
            self.config = config
        self.logger = logger
        self.strict = strict

        # Per-file PsychSim objects
        self.worlds = {}
        self.sources = set()

        # Accumulated AC data
        self.AC_data = {}
        self.AC_last = {}

        self.log_data = pandas.DataFrame()
        self.log_columns = None
        self.ac_columns = set()
        self.compliance_data = pandas.DataFrame()
        self.transcripts = {}

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
        if not isinstance(fname, list):
            fname = [fname]
        for f_index, f in enumerate(fname):
            self.logger.info(f'Processing file {f}')
            # if f_index == 0:
            #     transcript = get_transcript_name(f)
            #     if transcript is not None:
            #         trans_obj = Transcript(transcript)
            #         self.transcripts[filename_to_condition(f)['Team']] = trans_obj
            if f_index == 0:
                self.pre_replay(fname[0])
            else:
                self.worlds[f] = self.worlds[fname[0]]
            self.replay(f, num_steps)
            self.post_replay(f)

    def pre_replay(self, fname):
        logger_child = self.logger.getLogger(os.path.splitext(os.path.basename(fname))[0])
        self.worlds[fname] = ASISTWorld(config=self.config, logger=logger_child)
            
    def replay(self, fname, duration):
        conditions = filename_to_condition(fname)
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
                    if self.strict:
                        raise
                    else:
                        self.logger.error(traceback.format_exc())
                        self.logger.error(f'Error in reading line {line_no} of {fname}')
                        msg = None
                if msg:
                    self.sources.add(msg['msg']['source'])
                    if conditions['Team'] in self.transcripts:
                        self.transcripts[conditions['Team']].insert(msg)
                    try:
                        self.worlds[fname].process_msg(msg)
                    except Exception:
                        if self.strict:
                            raise
                        else:
                            self.logger.error(traceback.format_exc())
                            self.logger.error(f'Error in handling line {line_no} of {fname}')

    def post_replay(self, fname):
        for AC in self.worlds[fname].acs.values():
            if AC.last is not None:
                AC.data.to_csv(os.path.join(os.path.dirname(fname), 
                                            f'{self.worlds[fname].info["name"]}_{AC.name}.csv'))
                try:
                    self.AC_data[AC.name] = pandas.concat([self.AC_data[AC.name], AC.data], ignore_index=True)
                    self.AC_last[AC.name] = pandas.concat([self.AC_last[AC.name], AC.last], ignore_index=True)
                except KeyError:
                    self.AC_data[AC.name] = AC.data
                    self.AC_last[AC.name] = AC.last

        self.log_data = pandas.concat([self.log_data, self.worlds[fname].log_data], ignore_index=True)
        if self.log_columns is None:
            self.log_columns = self.worlds[fname].log_columns
        self.ac_columns |= self.worlds[fname].ac_columns
        if self.worlds[fname].compliance_data is not None:
            self.compliance_data = pandas.concat([self.compliance_data, self.worlds[fname].compliance_data],
                                                 ignore_index=True)
        if self.config.getboolean('output', 'psychsim', fallback=False):
            self.worlds[fname].save(os.path.splitext(fname)[0])
        self.worlds[fname].close()

    def pre_step(self, world):
        pass

    def post_step(self, world, actions, t, parser, debug):
        pass

    def finish(self):
        columns = self.log_columns
        if self.config.get('output', 'ac', fallback=False):
            columns += sorted(self.ac_columns)
        for col in columns:
            if col not in self.log_data.columns:
                self.log_data[col] = numpy.nan
        fname = self.config.get('output', 'file', fallback='interventions.csv')
        self.log_data.to_csv(fname, index=False, columns=columns)
        if self.config.get('output', 'ac', fallback=False):
            result = pandas.DataFrame(columns=['AC', 'variable', 'README'])
            new_rows = []
            for name, data in sorted(self.AC_data.items(), key=lambda tup: tup[0].lower()):
                if data is not None:
                    new_rows += [{'AC': name.split('_')[1].lower(), 
                                  'variable': col, 
                                  'README': AC_specs[name].get('README', None)}
                                 for col in data.drop(columns=['ASI', 'score', 'team', 'timestamp', 'trial']).columns]
                    # numeric = data.drop(columns=non_stats, errors='ignore')
                    # frame = numeric
                    # frame = frame.min().to_frame('min')
                    # frame = frame.join(numeric.max().to_frame('max'))
                    # frame = frame.join(numeric.mean().to_frame('mean'))
                    # frame = frame.join(numeric.std().to_frame('std'))
                    # numeric = self.AC_last[name].drop(columns=non_stats, errors='ignore')
                    # frame = frame.join(numeric.min().to_frame('min final'))
                    # frame = frame.join(numeric.max().to_frame('max final'))
                    # frame = frame.join(numeric.mean().to_frame('mean final'))
                    # frame = frame.join(numeric.std().to_frame('std final'))
                    # frame.insert(0, 'AC', name)
                    result = pandas.concat([result, pandas.DataFrame.from_records(new_rows)], ignore_index=True).drop_duplicates()
            result = result.sort_values(by=['AC', 'variable'], key=lambda col: col.str.lower())
            ac_fname = f'{os.path.splitext(fname)[0]}_ac.csv'
            result.to_csv(ac_fname, index=False)
        if self.config.getboolean('output', 'compliance', fallback=False):
            comply_fname = f'{os.path.splitext(fname)[0]}_comp.csv'
            self.compliance_data.to_csv(comply_fname, index=False)

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


def replay_parser(files_optional=False):
    parser = ArgumentParser()
    parser.add_argument('-o', '--output', help='Filename for output')
    parser.add_argument('--config', help='Config file specifying execution parameters')
    parser.add_argument('fname', nargs='*' if files_optional else '+',
                        help='Log file(s) (or directory of log files) to process')
    parser.add_argument('-1', '--1', action='store_true', help='Exit after the first run-through')
    parser.add_argument('-n', '--number', type=int, default=0,
                        help='Number of steps to replay (default is 0, meaning all)')
    parser.add_argument('-t', '--trials', type=int, nargs='*',
                        help='Trials to include (default is all)')
    parser.add_argument('-d', '--debug', default='WARNING', help='Level of logging detail')
    parser.add_argument('--profile', action='store_true', help='Run profiler')
    parser.add_argument('--clean', action='store_true', help='Delete older versions of data files')
    parser.add_argument('--strict', action='store_true', help='Throw exceptions without catching them')
    parser.add_argument('--ac', action='store_true', help='Add AC variables to the output')
    parser.add_argument('--decision', action='store_true', help='Add ASI decision inputs to the output')
    parser.add_argument('--hypothetical', action='store_true', help='Add ASI hypothetical interventions to the output')
    parser.add_argument('--compliance', action='store_true', help='Add compliance measures to the output')
    parser.add_argument('--psychsim', action='store_true', help='Save initial PsychSim world')
    parser.add_argument('--noactual', action='store_true', help='Do not add actual interventions to the output')
    parser.add_argument('--off', choices=['ac_cmu_ta2_ted', 'ac_cmu_ta2_beard', 'AC_CORNELL_TA2_TEAMTRUST', 'ac_gallup_ta2_gelp',
                                          'ac_ihmc_ta2_joint-activity-interdependence', 'AC_Rutgers_TA2_Utility',
                                          'ac_ucf_ta2_playerprofiler'], nargs='+')
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


def get_transcript_name(fname: str) -> str:
    """
    :return: The name of the transcript file associated with the given metadata file
    """
    conditions = filename_to_condition(fname)
    matches = glob.glob(os.path.join(os.path.dirname(fname), f'HSRData_ZoomAudioTranscript_Trial-na_Team-{conditions["Team"]}_Member-{conditions["Member"]}_CondBtwn-{"-".join(conditions["CondBtwn"])}_CondWin-{conditions["CondWin"]}_Vers-*.vtt'))
    try:
        return max(matches, key=lambda f: int(filename_to_condition(f)['Vers']))
    except ValueError:
        # No matches
        return None


if __name__ == '__main__':
    # Process command-line arguments
    args = parse_replay_args(replay_parser())
    config = configparser.ConfigParser()
    if args['config'] is not None:
        config.read(config)
    if 'output' not in config:
        config['output'] = {'actual': 'yes'}
    for field in ['ac', 'decision', 'hypothetical', 'compliance', 'psychsim']:
        if args[field]:
            config['output'][field] = 'yes'
    if args['noactual']:
        config['output']['actual'] = 'no'
    if args['output']:
        config['output']['file'] = args['output']
    if args['off'] is not None:
        if 'teamwork' not in config:
            config['teamwork'] = {}
        for name in args['off']:
            config['teamwork'][name] = 'no'
    replayer = Replayer(args['fname'], args['trials'], config=config, 
                        strict=args['strict'], clean=args['clean'], logger=logging)
    replayer.parameterized_replay(args)
