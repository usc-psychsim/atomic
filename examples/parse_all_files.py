import argparse
import copy
import os
from model_learning.util.io import get_files_with_extension, create_clear_dir, change_log_handler
from atomic.model_learning.linear.post_process.players_data import process_players_data
from atomic.model_learning.parser import TrajectoryParser
from atomic.parsing.replayer import Replayer, SUBJECT_ID_TAG, COND_MAP_TAG

__author__ = 'Pedro Sequeira'
__email__ = 'pedrodbs@gmail.com'
__desc__ = 'Simple test script that loads several player log files and creates a plot with the corresponding ' \
           'imported trajectories\' length.'

OUTPUT_DIR = 'output/parse-all-files'


class TrajectoryAnalyzer(Replayer):
    parser_class = TrajectoryParser

    def __init__(self, replays, maps=None, img_format='pdf'):
        super().__init__(replays, maps, {}, create_observer=False)
        self.img_format = img_format

        self.trajectories = {}
        self.subject_ids = {}
        self.agent_names = {}
        self.map_tables = {}
        self.trial_conditions = {}

    def post_replay(self):
        # registers trajectory and subject identifier
        self.logger.info(
            'Parsed trajectory of length {} for: {}'.format(len(self.parser.trajectory), self.parser.filename))
        self.trajectories[self.parser.filename] = self.parser.trajectory
        self.agent_names[self.parser.filename] = self.parser.player_name()
        self.map_tables[self.parser.filename] = self.map_table
        self.trial_conditions[self.parser.filename] = copy.deepcopy(self.conditions)

    def get_player_name(self, filename):
        # get player name if possible from the conditions dict
        conditions = self.trial_conditions[filename]
        if SUBJECT_ID_TAG in conditions and COND_MAP_TAG in conditions:
            return '{}-{}'.format(conditions[SUBJECT_ID_TAG], conditions[COND_MAP_TAG][0])
        return self.agent_names[filename]


if __name__ == '__main__':
    # parse command-line arguments
    parser = argparse.ArgumentParser(description=__desc__)

    parser.add_argument('-r', '--replays', required=True, type=str,
                        help='Directory containing the replay logs or single replay file to process.')
    parser.add_argument('-o', '--output', type=str, default=OUTPUT_DIR, help='Directory in which to save results.')
    args = parser.parse_args()

    # checks input files
    if os.path.isfile(args.replays):
        files = [args.replays]
    elif os.path.isdir(args.replays):
        files = list(get_files_with_extension(args.replays, 'csv'))
    else:
        raise ValueError('Input path is not a valid file or directory: {}.'.format(args.replays))

    # create output and log file
    create_clear_dir(args.output, False)
    change_log_handler(os.path.join(args.output, 'parsing.log'))

    # create replayer and process all files
    analyzer = TrajectoryAnalyzer(files)
    analyzer.process_files()

    # prints some charts about data
    process_players_data(analyzer, args.output)
