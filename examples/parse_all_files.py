import argparse
import os
from collections import OrderedDict
from atomic.definitions import world_map
from atomic.model_learning.parser import TrajectoryParser
from atomic.parsing.replayer import Replayer, SUBJECT_ID_TAG, COND_MAP_TAG
from model_learning.util.io import get_files_with_extension, create_clear_dir, change_log_handler
from model_learning.util.plot import plot_bar

__author__ = 'Pedro Sequeira'
__email__ = 'pedrodbs@gmail.com'
__desc__ = 'Simple test script that loads several player log files and creates a plot with the corresponding ' \
           'imported trajectories\' length.'

OUTPUT_DIR = 'output/parse-all-files'

# TODO hack to avoid lights
world_map.MODEL_LIGHTS = False


class TrajectoryAnalyzer(Replayer):
    parser_class = TrajectoryParser

    def __init__(self, replays, maps=None):
        super().__init__(replays, maps, {})

        self.trajectories = {}
        self.subject_ids = {}

    def post_replay(self):
        # registers trajectory and subject identifier
        self.logger.info(
            'Parsed trajectory of length {} for: {}'.format(len(self.parser.trajectory), self.parser.filename))
        self.trajectories[self.parser.filename] = self.parser.trajectory
        self.subject_ids[self.parser.filename] = \
            '{}-{}'.format(self.conditions[SUBJECT_ID_TAG], self.conditions[COND_MAP_TAG][0]) \
                if SUBJECT_ID_TAG in self.conditions and COND_MAP_TAG in self.conditions else \
                self.parser.player_name()


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
    change_log_handler(os.path.join(args.output, 'learning.log'))

    # create replayer and process all files
    analyzer = TrajectoryAnalyzer(files)
    analyzer.process_files()

    # creates plot with trajectories' lengths
    files = sorted(analyzer.trajectories.keys())
    lengths = [len(analyzer.trajectories[filename]) for filename in files]
    subject_ids = [analyzer.subject_ids[filename] for filename in files]
    traj_len_data = OrderedDict(zip(subject_ids, lengths))
    plot_bar(traj_len_data, 'Player Trajectory Length', os.path.join(args.output, 'length.pdf'), show=True)
