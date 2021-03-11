import argparse
import json
import os
import logging
import numpy as np
import multiprocessing as mp
from collections import OrderedDict
from timeit import default_timer as timer
from atomic.definitions.map_utils import get_default_maps
from atomic.model_learning.linear.rewards import create_reward_vector
from atomic.model_learning.parse_processor import TrajectoryParseProcessor
from atomic.parsing.replayer import Replayer, SUBJECT_ID_TAG, COND_MAP_TAG
from atomic.scenarios.single_player import make_single_player_world
from model_learning.trajectory import generate_trajectories
from model_learning.util.cmd_line import none_or_int
from model_learning.util.plot import plot_bar
from model_learning.util.io import get_files_with_extension, create_clear_dir, change_log_handler

__author__ = 'Pedro Sequeira'
__email__ = 'pedrodbs@gmail.com'
__desc__ = 'Simple test script that loads several player log files and creates a plot with the corresponding ' \
           'imported trajectories\' length.'

OUTPUT_DIR = 'output/benchmark'

# params
NUM_TRAJECTORIES = 0
TRAJ_LENGTH = 10  # 15
RATIONALITY = 1 / 0.1  # inverse temperature
SELECTION = 'distribution'
PRUNE_THRESHOLD = 5e-2  # 1e-2
KEEP_K = 10
HORIZON = 2
SEED = 0
PROCESSES = None

MAP_NAME = 'FalconEasy'
PLAYER_NAME = 'Player'
FULL_OBS = True

REWARD_WEIGHTS = np.array([
    0,  # Before Mid
    0,  # After Mid
    0,  # Loc Freq
    0.5,  # Triaged Green
    0.5,  # Triaged Gold
    0,  # See White
    0,  # See Red
    0,  # Move N
    0,  # Move E
    0,  # Move S
    0  # Move W
])


def _signal_traj_completion():
    logging.info('\tTrajectory generation complete.')


class BenchmarkReplayer(Replayer):

    def __init__(self, replays, maps=None):
        super().__init__(replays, maps, {}, create_observer=False, processor=TrajectoryParseProcessor())

        self.timings = {}
        self.subject_ids = {}
        self.trajectories = {}

    def replay(self, duration, logger):
        start = timer()
        super(BenchmarkReplayer, self).replay(duration, logger)
        elapsed = timer() - start
        self.logger.info('Parsed {} in {:.3f}s'.format(self.parser.filename, elapsed))
        self.subject_ids[self.parser.filename] = \
            '{}-{}'.format(self.conditions[SUBJECT_ID_TAG], self.conditions[COND_MAP_TAG][0]) \
                if SUBJECT_ID_TAG in self.conditions and COND_MAP_TAG in self.conditions else \
                self.parser.player_name()
        self.timings[self.parser.filename] = elapsed
        self.trajectories[self.parser.filename] = self.processor.trajectory


if __name__ == '__main__':
    # parse command-line arguments
    parser = argparse.ArgumentParser(description=__desc__)

    parser.add_argument('-o', '--output', type=str, default=OUTPUT_DIR, help='Directory in which to save results.')
    parser.add_argument('-r', '--replays', type=str, default=None,
                        help='Directory containing the replay logs or single replay file to process.')
    parser.add_argument('-t', '--trajectories', type=int, default=NUM_TRAJECTORIES,
                        help='Number of trajectories to use in reward learning.')
    parser.add_argument('-l', '--length', type=int, default=TRAJ_LENGTH,
                        help='Length of trajectories used in reward learning.')
    parser.add_argument('--horizon', type=int, default=HORIZON, help='Planning horizon of the agent.')
    parser.add_argument('--rationality', type=float, default=RATIONALITY, help='Agent\'s rationality.')
    parser.add_argument('--selection', type=str, default=SELECTION, help='Agent\'s selection policy.')
    parser.add_argument('--prune', type=float, default=PRUNE_THRESHOLD,
                        help='Likelihood below which stochastic outcomes are pruned.')

    parser.add_argument('-s', '--seed', type=int, default=SEED, help='Seed for random number generation.')
    parser.add_argument('-m', '--map-name', type=str, default=MAP_NAME,
                        help='Name of the map for trajectory generation.')
    parser.add_argument('-p', '--processes', type=none_or_int, default=PROCESSES,
                        help='Number of processes/cores to use. If unspecified, all available cores will be used')
    args = parser.parse_args()

    # create output and log file
    create_clear_dir(args.output, False)
    change_log_handler(os.path.join(args.output, 'learning.log'))

    # saves args
    with open(os.path.join(args.output, 'args.json'), 'w') as fp:
        json.dump(vars(args), fp, indent=4)

    # checks input files
    files = []
    if args.replays is None:
        logging.info('No replay file provided, skipping parsing benchmark.'.format(args.replays))
    elif os.path.isfile(args.replays):
        files = [args.replays]
    elif os.path.isdir(args.replays):
        files = list(get_files_with_extension(args.replays, 'csv'))
    else:
        logging.info('Provided replay path is not a valid file or directory: {}.'.format(args.replays))

    # create replayer and process all files
    if len(files) > 0:
        replayer = BenchmarkReplayer(files)
        replayer.process_files()

        files = sorted(replayer.trajectories.keys())
        lengths = np.array([len(replayer.trajectories[filename]) for filename in files])
        times = np.array([replayer.timings[filename] for filename in files])
        logging.info('Parsing of {} files took a total of {:.3f}s (mean: {:.3f}s per file, {:.3f}s per step)'.format(
            len(replayer.timings), np.sum(times), np.mean(times), np.mean(times / lengths)))

        # prints results
        files = sorted(replayer.timings.keys())
        times = [replayer.timings[filename] for filename in files]
        subject_ids = [replayer.subject_ids[filename] for filename in files]
        plot_bar(OrderedDict(zip(subject_ids, times)), 'Parsing Times', os.path.join(args.output, 'parse-times.pdf'))
        plot_bar(OrderedDict(zip(subject_ids, lengths)), 'Trajectory Lengths',
                 os.path.join(args.output, 'parse-lengths.pdf'))

    # generate trajectories
    default_maps = get_default_maps()
    if args.trajectories == 0 or args.map_name not in default_maps:
        msg = 'Skipping generation benchmark. '
        if args.map_name not in default_maps:
            msg += 'Map name {} not in default maps.'.format(args.map_name)
        logging.info(msg)

    else:
        # create world, agent and observer
        map_table = default_maps[args.map_name]
        world, agent, observer, victims, world_map = make_single_player_world(
            PLAYER_NAME, map_table.init_loc, map_table.adjacency, map_table.victims,
            False, FULL_OBS, False)

        # agent params
        agent.setAttribute('rationality', args.rationality)
        agent.setAttribute('selection', args.selection)
        agent.setAttribute('horizon', args.horizon)

        # set agent rwd function
        rwd_vector = create_reward_vector(agent, map_table.rooms_list, world_map.moveActions[agent.name])
        rwd_vector.set_rewards(agent, REWARD_WEIGHTS)
        logging.info('Set reward vector: {}'.format(dict(zip(rwd_vector.names, REWARD_WEIGHTS))))

        # generate trajectories
        logging.info('Generating {} trajectories of length {} using {} parallel processes...'.format(
            args.trajectories, args.length, args.processes if args.processes is not None else mp.cpu_count()))
        start = timer()
        trajectories = generate_trajectories(
            agent, args.trajectories, args.length, threshold=args.prune, processes=args.processes, seed=args.seed,
            verbose=True)

        elapsed = timer() - start
        logging.info('(mean: {:.3f}s per trajectory, {:.3f}s per step)'.format(
            elapsed / args.trajectories, elapsed / (args.trajectories * args.length)))
