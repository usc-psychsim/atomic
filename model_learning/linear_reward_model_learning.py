import argparse
import json
import logging
import os
import random
import numpy as np
from model_learning.metrics import evaluate_internal
from model_learning.planning import get_policy
from model_learning.trajectory import sample_sub_trajectories
from model_learning.util import str2bool
from model_learning.util.io import create_clear_dir, get_file_name_without_extension, save_object
from model_learning.algorithms.max_entropy import MaxEntRewardLearning, THETA_STR
from atomic_domain_definitions.SandRMap import getSandRMap, getSandRVictims, getSandRCoords
from atomic_domain_definitions.maker import makeWorld
from locations_no_pre import Locations
from atomic_domain_definitions.parser_no_pre import TrajectoryParser
from atomic_domain_definitions.model_learning.utils import get_participant_data_props as gpdp
from atomic_domain_definitions.model_learning.rewards import create_reward_vector
from atomic_domain_definitions.plotting import plot, plot_trajectories, plot_location_frequencies, \
    plot_action_frequencies

__author__ = 'Pedro Sequeira'
__email__ = 'pedrodbs@gmail.com'
__desc__ = ''

LEARNED_BEST_THETA = np.array([0.01, 0.03, -0.29, -0.07, 0.07, 0.05, -0.01, 0.16, -0.02, -0.22, 0.02])

# trajectory params
NUM_TRAJECTORIES = os.cpu_count()  # 8 # 20
TRAJ_LENGTH = 10  # 15
PRUNE_THRESHOLD = 5e-2  # 1e-2
SEED = 0

# learning algorithm params
HORIZON = 2
NORM_THETA = True
LEARNING_RATE = 5e-2  # 1e-2
MAX_EPOCHS = 50  # 100  # 200
DIFF_THRESHOLD = 1e-2  # 5e-3  # 1e-3

# data params
DATA_FILE_IDX = 5
FULL_OBS = False

OUTPUT_DIR = 'output/linear-reward-learning'
PROCESSES = None
IMG_FORMAT = 'pdf'  # 'png'

AGENT_RATIONALITY = 1 / 0.1  # inverse temperature

if __name__ == '__main__':

    # parse command-line arguments
    parser = argparse.ArgumentParser(description=__desc__)
    parser.add_argument('-t', '--trajectories', type=int, default=NUM_TRAJECTORIES,
                        help='Number of trajectories to use in reward learning.')
    parser.add_argument('-l', '--length', type=int, default=TRAJ_LENGTH,
                        help='Length of trajectories used in reward learning.')
    parser.add_argument('-hz', '--horizon', type=int, default=HORIZON, help='Planning horizon of the "learner" agent.')
    parser.add_argument('-e', '--epochs', type=int, default=MAX_EPOCHS,
                        help='The maximum number of gradient descent steps.')
    parser.add_argument('-lr', '--learn-rate', type=float, default=LEARNING_RATE,
                        help='The gradient descent learning/update rate.')
    parser.add_argument('-nw', '--normalize', type=str2bool, default=NORM_THETA,
                        help='Whether to normalize reward weights at each step of the algorithm.')
    parser.add_argument('-pt', '--prune', type=float, default=PRUNE_THRESHOLD,
                        help='Likelihood below which stochastic outcomes are pruned.')
    parser.add_argument('-dt', '--diff', type=float, default=DIFF_THRESHOLD,
                        help='The termination threshold for the weight vector difference.')
    parser.add_argument('-o', '--output', type=str, default=OUTPUT_DIR, help='Directory in which to save results.')
    parser.add_argument('-c', '--clear', help='Whether to clear output directories before generating results.',
                        action='store_true')
    parser.add_argument('-p', '--processes', type=int, default=PROCESSES,
                        help='Number of processes/cores to use. If unspecified, all available cores will be used')
    parser.add_argument('-v', '--verbosity', action='count', default=0, help='Verbosity level.')
    parser.add_argument('--format', help='Format of images', default=IMG_FORMAT)
    parser.add_argument('-s', '--seed', type=int, default=SEED, help='Seed for random number generation.')
    args = parser.parse_args()

    # sets general random seeds
    random.seed(args.seed)
    np.random.seed(args.seed)

    # prepare input data
    pdp = gpdp()
    pdp_itm = DATA_FILE_IDX
    data_filename = pdp[pdp_itm]['fname']
    traj_start = pdp[pdp_itm]['start']
    traj_stop = pdp[pdp_itm]['stop']

    # create output
    output_dir = os.path.join(args.output, get_file_name_without_extension(data_filename))
    create_clear_dir(output_dir, args.clear)

    # saves args
    with open(os.path.join(output_dir, 'args.json'), 'w') as fp:
        json.dump(vars(args), fp, indent=4)

    # sets up log to file
    log_level = logging.WARN if args.verbosity == 0 else logging.INFO if args.verbosity == 1 else logging.DEBUG
    logging.basicConfig(
        handlers=[logging.StreamHandler(), logging.FileHandler(os.path.join(output_dir, 'learning.log'), 'w')],
        format='%(message)s', level=log_level)

    # parse data
    logging.info('Parsing data file {} from {} to {}...'.format(data_filename, traj_start, traj_stop))
    parser = TrajectoryParser(data_filename)
    player_name = parser.data['player_ID'].iloc[0]
    logging.info('Got {} events for player "{}"'.format(parser.data.shape[0], player_name))

    # create world, agent and observer
    neighbors = getSandRMap()
    locations = list(neighbors.keys())
    coordinates = getSandRCoords()
    world, agent, _, victims_obj = makeWorld(player_name, 'BH2', neighbors, getSandRVictims(), False, FULL_OBS)
    plot(world, locations, neighbors, os.path.join(output_dir, 'env.{}'.format(args.format)), coordinates)

    # get trajectory from player data
    parser.victimsObj = victims_obj
    aes, _ = parser.getActionsAndEvents(agent.name, args.verbosity > 0)
    logging.info('=================================')
    logging.info('Getting trajectory out of {} actions/events...'.format(len(aes)))
    if traj_stop == -1:
        traj_stop = len(aes)
    parser.runTimeless(world, agent.name, aes, traj_start, traj_stop, len(aes), args.prune, True)
    trajectory = parser.trajectory
    logging.info('Recorded {} state-action pairs'.format(len(trajectory)))
    save_object(trajectory, os.path.join(output_dir, 'trajectory.pkl.gz'))
    plot_trajectories(agent, locations, neighbors, [trajectory],
                      os.path.join(output_dir, 'trajectory.{}'.format(args.format)), coordinates,
                      title='Player Trajectory')
    plot_location_frequencies(
        agent, locations, os.path.join(output_dir, 'loc-frequencies.{}'.format(args.format)), [trajectory])
    plot_action_frequencies(
        agent, os.path.join(output_dir, 'action-frequencies.{}'.format(args.format)), [trajectory])

    # collect sub-trajectories from player's trajectory
    trajectories = sample_sub_trajectories(trajectory, args.trajectories, args.length, seed=args.seed)
    logging.info('Collected {} trajectories of length {} from original trajectory.'.format(
        args.trajectories, args.length))
    plot_trajectories(agent, locations, neighbors, trajectories,
                      os.path.join(output_dir, 'sub-trajectories.{}'.format(args.format)), coordinates,
                      title='Training Sub-Trajectories')
    trajectories = [[(w.state, a) for w, a in t] for t in trajectories]

    # create reward vector and optimize reward weights via MaxEnt IRL
    logging.info('=================================')
    logging.info('Starting Maximum Entropy IRL optimization...')
    rwd_vector = create_reward_vector(agent, Locations.AllLocations, Locations.moveActions[agent.name])
    alg = MaxEntRewardLearning(
        'max-ent', agent, rwd_vector,
        args.processes, args.normalize, args.learn_rate, args.epochs, args.diff, args.prune, args.horizon, args.seed)
    stats = alg.learn(trajectories, args.verbosity > 0)

    # saves results/stats
    alg.save_results(stats, output_dir, args.format)

    rwd_vector.set_rewards(agent, stats[THETA_STR])
    # rwd_vector.set_rewards(agent, LEARNED_BEST_THETA)
    learner_r = next(iter(agent.getReward().values()))
    logging.info('Optimized reward function:\n\n{}'.format(learner_r))

    logging.info('=================================')

    # player's observed "policy"
    logging.info('Collecting observed player policy...')
    player_states = [w.state for w, _ in trajectory]
    player_pi = [a for _, a in trajectory]

    # compute learner's policy
    logging.info('Computing policy with learned reward for {} states...'.format(len(player_states)))
    agent.setAttribute('rationality', AGENT_RATIONALITY)
    learner_pi = get_policy(agent, player_states, None, args.horizon, 'distribution', args.prune, args.processes)

    logging.info('Computing evaluation metrics...')
    metrics = evaluate_internal(player_pi, learner_pi)
    logging.info('Results:')
    for name, metric in metrics.items():
        logging.info('\t{}: {:.3f}'.format(name, metric))

    logging.info('\nFinished!')
