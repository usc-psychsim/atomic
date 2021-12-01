import json
import os
import logging
import numpy as np
import multiprocessing as mp
from collections import OrderedDict
from timeit import default_timer as timer
from psychsim.pwl import stateKey
from atomic.parsing.replayer import Replayer, COND_MAP_TAG, TEAM_ID_TAG, replay_parser, parse_replay_args, \
    filename_to_condition
from atomic.util.io import create_clear_dir, change_log_handler
from atomic.util.plot import plot_bar
from rddl2psychsim.conversion.converter import Converter
from model_learning.trajectory import generate_trajectories, copy_world

__author__ = 'Pedro Sequeira'
__email__ = 'pedrodbs@gmail.com'
__desc__ = 'Simple test script that loads several team log files and creates a plot with the corresponding ' \
           'imported trajectories\' length, processing times, etc.'

LOG_EXTENSION = 'metadata'
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
PROCESSES = -1

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

    def __init__(self):
        super().__init__(args['fname'], rddl_file=args['rddl'], action_file=args['actions'], aux_file=args['aux'])
        # per file stats
        self.timings = {}
        self.ids = {}
        self.trajectories = {}
        self.total_lengths = {}

        # current file stats
        self.trajectory = []
        self.step_times = []
        self.prev_world = None
        self.start = -1.

    def pre_step(self, world, parser, logger=logging):
        self.prev_world = copy_world(world)  # todo change agent world cloning
        self.start = timer()

    def post_step(self, world, actions, t, parser, debug, logger=logging):
        elapsed = timer() - self.start
        self.logger.info(f'Step {len(self.trajectory)}: {elapsed:.3f}s')
        self.step_times.append(elapsed)
        self.trajectory.append((self.prev_world, actions))

    def replay(self, parser, rddl_converter, duration, logger):
        # reset
        self.trajectory = []
        self.step_times = []
        self.prev_world = None
        self.start = 0.
        start = timer()
        try:
            exception = None
            super(BenchmarkReplayer, self).replay(parser, rddl_converter, duration, logger)
        except Exception as e:
            exception = e

        # process results
        elapsed = timer() - start
        self.logger.info(f'Parsed {parser.filename} in {elapsed:.3f}s')
        conditions = filename_to_condition(parser.filename)
        self.ids[parser.filename] = \
            '{}-{}'.format(conditions[TEAM_ID_TAG], conditions[COND_MAP_TAG][0]) \
                if TEAM_ID_TAG in conditions and COND_MAP_TAG in conditions else \
                os.path.basename(parser.filename)
        self.timings[parser.filename] = elapsed
        self.trajectories[parser.filename] = self.trajectory
        self.total_lengths[parser.filename] = len(parser.actions)

        if exception is not None:
            raise exception


def _generate_trajectories():
    # create world & agents from RDDL
    rddl_converter = Converter()
    rddl_converter.convert_file(rddl_file=args['rddl'])
    world = rddl_converter.world

    # set params to the first agent, other's decide at random
    agent = next(iter(world.agents.values()))
    for ag in world.agents.values():
        if ag != agent:
            ag.setAttribute('selection', 'random')
            ag.setAttribute('horizon', 0)
    agent.setAttribute('rationality', args['rationality'])
    agent.setAttribute('selection', args['selection'])
    agent.setAttribute('horizon', args['horizon'])

    # TODO set agent rwd function
    # rwd_vector = create_reward_vector(agent, map_table.rooms_list, world_map.moveActions[agent.name])
    # rwd_vector.set_rewards(agent, REWARD_WEIGHTS)
    # logging.info('Set reward vector: {}'.format(dict(zip(rwd_vector.names, REWARD_WEIGHTS))))

    # randomize initial location
    features = [stateKey(agent.name, 'pLoc')]

    # generate trajectories
    n_procs = args['processes'] if args['processes'] > 0 else mp.cpu_count()
    logging.info(f'Generating {args["trajectories"]} trajectories of length {args["length"]} '
                 f'using {n_procs} parallel processes...')
    start = timer()
    trajectories = generate_trajectories(
        agent, args['trajectories'], args['length'],
        features=features,
        select=None,
        threshold=args['prune'],
        processes=n_procs,
        seed=args['seed'],
        verbose=True)
    elapsed = (timer() - start) * n_procs

    logging.info('(mean: {:.3f}s per trajectory, {:.3f}s per step)'.format(
        elapsed / args['trajectories'], elapsed / (args['trajectories'] * args['length'])))


def _process_files():
    replayer.process_files()

    files = sorted(replayer.trajectories.keys())
    lengths = np.array([len(replayer.trajectories[filename]) for filename in files])
    times = np.array([replayer.timings[filename] for filename in files])
    logging.info('Parsing of {} files took a total of {:.3f}s (mean: {:.3f}s per file, {:.3f}s per step)'.format(
        len(replayer.timings), np.sum(times), np.mean(times), np.mean(times / lengths)))

    # prints results
    files = sorted(replayer.timings.keys())
    times = [replayer.timings[filename] for filename in files]
    ids = [replayer.ids[filename] for filename in files]
    perc_parsed = ((lengths / np.array([replayer.total_lengths[filename] for filename in files])) * 100).astype(int)
    plot_bar(OrderedDict(zip(ids, times)), 'Processing Times', os.path.join(args['output'], 'process-times.pdf'))
    plot_bar(OrderedDict(zip(ids, lengths)), 'Parsed Lengths', os.path.join(args['output'], 'parse-lengths.pdf'))
    plot_bar(OrderedDict(zip(ids, perc_parsed)), 'Parsed Percentage', os.path.join(args['output'], 'parse-percent.pdf'))
    overall_stats = {'Processing Times': (np.mean(times), np.std(times)),
                     'Parsed Lengths': (np.mean(lengths), np.std(lengths)),
                     'Parsed Percentage': (np.mean(perc_parsed), np.std(perc_parsed))}
    plot_bar(overall_stats, 'Average Stats', os.path.join(args['output'], 'overall-stats.pdf'), plot_mean=False)


if __name__ == '__main__':
    # parse command-line arguments
    parser = replay_parser()
    parser.description = __desc__

    parser.add_argument('-o', '--output', type=str, default=OUTPUT_DIR, help='Directory in which to save results.')
    parser.add_argument('-tr', '--trajectories', type=int, default=NUM_TRAJECTORIES,
                        help='Number of trajectories to generate in benchmarking.')
    parser.add_argument('-l', '--length', type=int, default=TRAJ_LENGTH,
                        help='Length of trajectories used to generate in benchmarking.')
    parser.add_argument('--horizon', type=int, default=HORIZON, help='Planning horizon of the agent.')
    parser.add_argument('--rationality', type=float, default=RATIONALITY, help='Agent\'s rationality.')
    parser.add_argument('--selection', type=str, default=SELECTION, help='Agent\'s selection policy.')
    parser.add_argument('--prune', type=float, default=PRUNE_THRESHOLD,
                        help='Likelihood below which stochastic outcomes are pruned.')

    parser.add_argument('-s', '--seed', type=int, default=SEED, help='Seed for random number generation.')
    parser.add_argument('-p', '--processes', type=int, default=PROCESSES,
                        help='Number of processes/cores to use. If unspecified, all available cores will be used.')

    args = parse_replay_args(parser)

    # create output and log file
    create_clear_dir(args['output'], False)
    change_log_handler(os.path.join(args['output'], 'learning.log'), verbosity=args['debug'])

    # saves args
    with open(os.path.join(args['output'], 'args.json'), 'w') as fp:
        json.dump(args, fp, indent=4)

    # create replayer and process all files
    replayer = BenchmarkReplayer()
    if len(replayer.files) == 0:
        logging.info('Skipping game logs processing benchmark.')
    else:
        _process_files()

    # generate trajectories
    if args['trajectories'] == 0:
        logging.info('Skipping trajectory generation benchmark.')
    else:
        _generate_trajectories()
