import argparse
import logging
import os
import pandas as pd
import matplotlib.pyplot as plt
from model_learning.util.io import create_clear_dir

__author__ = 'Pedro Sequeira'
__email__ = 'pedrodbs@gmail.com'
__desc__ = 'Loads a file with the rectangular coordinates of rooms and computes the normalized room coordinates, which ' \
           'are saved in a CSV file.'

OUTPUT_DIR = 'output/coords'

ROOM_ID_COL = 'RoomID'
X0_COORD_COL = 'x0'
X1_COORD_COL = 'x1'
Z0_COORD_COL = 'z0'
Z1_COORD_COL = 'z1'

if __name__ == '__main__':
    # parse command-line arguments
    parser = argparse.ArgumentParser(description=__desc__)

    parser.add_argument('-i', '--input', required=True, type=str,
                        help='File with the rooms rectangular coordinates.')
    parser.add_argument('-o', '--output', type=str, default=OUTPUT_DIR, help='Directory in which to save results.')
    parser.add_argument('-c', '--clear', help='Whether to clear output directory before generating results.',
                        action='store_true')
    parser.add_argument('-v', '--verbosity', action='count', default=0, help='Verbosity level.')
    args = parser.parse_args()

    # sets up log to file
    log_level = logging.WARN if args.verbosity == 0 else logging.INFO if args.verbosity == 1 else logging.DEBUG
    logging.basicConfig(format='%(message)s', level=log_level)

    # create output
    create_clear_dir(args.output, args.clear)

    # checks input file
    if not os.path.isfile(args.input):
        raise ValueError('Input file is not valid: {}.'.format(args.input))

    logging.info('Processing room file: "{}"...'.format(args.input))
    df = pd.read_csv(args.input, index_col=0)

    # get rooms' means
    df['x'] = 0.5 * (df[X0_COORD_COL] + df[X1_COORD_COL])
    df['y'] = 0.5 * (df[Z0_COORD_COL] + df[Z1_COORD_COL])

    # min-max scale coords
    df['x'] = (df['x'] - df['x'].min()) / (df['x'].max() - df['x'].min())
    df['y'] = (df['y'] - df['y'].min()) / (df['y'].max() - df['y'].min())

    plt.figure()
    plt.scatter(df['x'],df['y'])
    plt.show()
    plt.close()

    # get horizontal and vertical num. rooms
    num_horiz = len(df[df['x'] == df['x'].min()])

    logging.info('Finished!')
