import argparse
import logging
import os
import pandas as pd
from model_learning.util.io import create_clear_dir, get_files_with_extension

__author__ = 'Pedro Sequeira'
__email__ = 'pedrodbs@gmail.com'
__desc__ = 'Loads several player log files and generates sequential player ids.'

OUTPUT_DIR = 'output/logs'
PLAYER_ID_COL = 'player_ID'
PLAYER_PREFIX = 'Player'

if __name__ == '__main__':
    # parse command-line arguments
    parser = argparse.ArgumentParser(description=__desc__)

    parser.add_argument('-r', '--replays', required=True, type=str,
                        help='Directory containing the replay logs or single replay file to process.')
    parser.add_argument('-o', '--output', type=str, default=OUTPUT_DIR, help='Directory in which to save results.')
    parser.add_argument('-c', '--clear', help='Whether to clear output directories before generating results.',
                        action='store_true')
    parser.add_argument('-s', '--start', type=int, default=0, help='ID from which to start numbering.')
    parser.add_argument('-v', '--verbosity', action='count', default=0, help='Verbosity level.')
    args = parser.parse_args()

    # sets up log to file
    log_level = logging.WARN if args.verbosity == 0 else logging.INFO if args.verbosity == 1 else logging.DEBUG
    logging.basicConfig(format='%(message)s', level=log_level)

    # create output
    output_dir = os.path.join(args.output, os.path.basename(args.replays))
    create_clear_dir(output_dir, args.clear)

    # checks input files
    if os.path.isfile(args.replays):
        files = [args.replays]
    elif os.path.isdir(args.replays):
        files = list(get_files_with_extension(args.replays, 'csv'))
    else:
        raise ValueError('Input path is not a valid file or directory: {}.'.format(args.replays))

    logging.info('Processing {} log files from "{}"...'.format(len(files), args.replays))

    for i, file in enumerate(files):
        df = pd.read_csv(file, index_col=0)
        old_id = set(df[PLAYER_ID_COL])
        assert len(old_id) == 1, 'Multiple players defined in "{}"!'.format(file)

        new_id = '{}_{}'.format(PLAYER_PREFIX, i + args.start)
        df[PLAYER_ID_COL] = new_id
        df.to_csv(os.path.join(output_dir, os.path.basename(file)))
        logging.info('Processed "{}" old player id: {}, new player id: {}'.format(file, old_id, new_id))
