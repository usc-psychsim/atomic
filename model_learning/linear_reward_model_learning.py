import logging
import os
import numpy as np
from model_learning.metrics import policy_mismatch_prob, policy_divergence
from model_learning.planning import get_policy
from model_learning.trajectory import sample_sub_trajectories
from model_learning.util.plot import plot_evolution
from model_learning.util.io import create_clear_dir, get_file_name_without_extension
from model_learning.algorithms.max_entropy import MaxEntRewardLearning, FEATURE_COUNT_DIFF_STR, REWARD_WEIGHTS_STR, \
    THETA_STR, TIME_STR
from atomic_domain_definitions.SandRMap import getSandRMap, getSandRVictims, getSandRCoords
from atomic_domain_definitions.maker import makeWorld
from locations_no_pre import Locations
from atomic_domain_definitions.parser_no_pre import DataParser
from atomic_domain_definitions.model_learning.utils import get_participant_data_props as gpdp
from atomic_domain_definitions.model_learning.rewards import create_reward_vector
from atomic_domain_definitions.plotting import plot, plot_trajectories, plot_location_frequencies, \
    plot_action_frequencies

__author__ = 'Pedro Sequeira'
__email__ = 'pedrodbs@gmail.com'
__description__ = ''

LEARNED_BEST_THETA = np.array([0.01, 0.03, -0.29, -0.07, 0.07, 0.05, -0.01, 0.16, -0.02, -0.22, 0.02])

# trajectory params
NUM_TRAJECTORIES = 8  # 8  # 20
TRAJ_LENGTH = 10  # 15
PRUNE_THRESHOLD = 1e-2
SEED = 0

# learning algorithm params
HORIZON = 2
NORM_THETA = True
LEARNING_RATE = 5e-2  # 1e-2
MAX_EPOCHS = 100  # 200
DIFF_THRESHOLD = 1.5#1e-2  # 5e-3  # 1e-3
LEARNING_SEED = 1

# data params
DATA_FILE_IDX = 0
FULL_OBS = False

OUTPUT_DIR = 'output/linear-reward-learning'
PARALLEL = True
DEBUG = False
CLEAR = True
IMG_FORMAT = 'pdf'  # 'png'

AGENT_RATIONALITY = 1 / 0.1  # inverse temperature


def _get_feature_vector(state):
    """
    Gets the feature count vector associated with the given state.
    :param VectorDistributionSet state: the PsychSim state for which to get the feature matrix.
    :rtype: np.ndarray
    :return: the feature count vector.
    """
    global rwd_vector
    return rwd_vector.get_values(state)


def _set_reward_function(theta, ag):
    """
    Sets a reward to the agent that is a linear combination of the given weights associated with each feature.
    :param np.ndarray theta: the reward weights associated with each feature.
    :param Agent ag: the agent to whom the reward is going to be set.
    :return:
    """
    global rwd_vector
    ag.setAttribute('R', {})
    rwd_vector.set_rewards(ag, theta)


if __name__ == '__main__':

    # prepare input data
    pdp = gpdp()
    pdp_itm = DATA_FILE_IDX
    data_filename = pdp[pdp_itm]['fname']
    traj_start = pdp[pdp_itm]['start']
    traj_stop = pdp[pdp_itm]['stop']

    # create output
    output_dir = os.path.join(OUTPUT_DIR, get_file_name_without_extension(data_filename))
    create_clear_dir(output_dir, CLEAR)

    # sets up log to file
    logging.basicConfig(
        handlers=[logging.StreamHandler(), logging.FileHandler(os.path.join(output_dir, 'learning.log'), 'w')],
        format='%(message)s', level=logging.DEBUG if DEBUG else logging.INFO)

    # parse data
    logging.info('Parsing data file {} from {} to {}...'.format(data_filename, traj_start, traj_stop))
    parser = DataParser(data_filename)
    player_name = parser.data['player_ID'].iloc[0]
    logging.info('Got {} events for player "{}"'.format(parser.data.shape[0], player_name))

    # create world, agent and observer
    neighbors = getSandRMap()
    locations = list(neighbors.keys())
    coordinates = getSandRCoords()
    world, agent, _, victims_obj = makeWorld(player_name, 'BH2', neighbors, getSandRVictims(), False, FULL_OBS)
    plot(world, locations, neighbors, os.path.join(output_dir, 'env.{}'.format(IMG_FORMAT)), coordinates)

    # get trajectory from player data
    parser.victimsObj = victims_obj
    aes, _ = parser.getActionsAndEvents(agent.name, DEBUG)
    logging.info('=================================')
    logging.info('Getting trajectory out of {} actions/events...'.format(len(aes)))
    if traj_stop == -1:
        traj_stop = len(aes)
    trajectory = []
    parser.runTimeless(world, agent.name, aes, traj_start, traj_stop, len(aes), trajectory, PRUNE_THRESHOLD)
    logging.info('Recorded {} state-action pairs'.format(len(trajectory)))
    plot_trajectories(agent, locations, neighbors, [trajectory],
                      os.path.join(output_dir, 'trajectory.{}'.format(IMG_FORMAT)), coordinates,
                      title='Player Trajectory')
    plot_location_frequencies(
        agent, locations, os.path.join(output_dir, 'loc-frequencies.{}'.format(IMG_FORMAT)), [trajectory])
    plot_action_frequencies(
        agent, os.path.join(output_dir, 'action-frequencies.{}'.format(IMG_FORMAT)), [trajectory])

    # collect sub-trajectories from player's trajectory
    trajectories = sample_sub_trajectories(trajectory, NUM_TRAJECTORIES, TRAJ_LENGTH, seed=SEED)
    logging.info('Collected {} trajectories of length {} from original trajectory.'.format(
        NUM_TRAJECTORIES, TRAJ_LENGTH))
    plot_trajectories(agent, locations, neighbors, trajectories,
                      os.path.join(output_dir, 'sub-trajectories.{}'.format(IMG_FORMAT)), coordinates,
                      title='Training Sub-Trajectories')

    # create reward vector and optimize reward weights via MaxEnt IRL
    logging.info('=================================')
    logging.info('Starting Maximum Entropy IRL optimization...')
    rwd_vector = create_reward_vector(agent, Locations.AllLocations, Locations.moveActions[agent.name])
    alg = MaxEntRewardLearning(
        'max-ent', agent, len(rwd_vector), _get_feature_vector, _set_reward_function,
        None if PARALLEL else 1, NORM_THETA, LEARNING_RATE, MAX_EPOCHS, DIFF_THRESHOLD, PRUNE_THRESHOLD, LEARNING_SEED)
    trajectories = [[(w.state, a) for w, a in t] for t in trajectories]
    stats = alg.learn(trajectories, True)
    logging.info('Finished, total time: {:.2f} secs.'.format(stats[TIME_STR].sum()))

    _set_reward_function(stats[THETA_STR], agent)
    # _set_reward_function(LEARNED_BEST_THETA, agent)
    learner_r = next(iter(agent.getReward().values()))
    logging.info('Optimized reward function:\n\n{}'.format(learner_r))

    # saves results/stats
    np.savetxt(os.path.join(output_dir, 'learner-theta.csv'), stats[THETA_STR].reshape(1, -1), '%s', ',',
               header=','.join(rwd_vector.names), comments='')
    plot_evolution(stats[FEATURE_COUNT_DIFF_STR], ['diff'], 'Feature Count Diff. Evolution', None,
                   os.path.join(output_dir, 'evo-feat-diff.{}'.format(IMG_FORMAT)), 'Epoch', 'Feature Difference')
    plot_evolution(stats[REWARD_WEIGHTS_STR], rwd_vector.names, 'Reward Parameters Evolution', None,
                   os.path.join(output_dir, 'evo-rwd-weights.{}'.format(IMG_FORMAT)), 'Epoch', 'Weight')
    plot_evolution(stats[TIME_STR], ['time'], 'Step Time Evolution', None,
                   os.path.join(output_dir, 'evo-time.{}'.format(IMG_FORMAT)), 'Epoch', 'Time (secs.)')

    logging.info('=================================')

    # player's observed "policy"
    logging.info('Collecting observed player policy...')
    player_states = [w.state for w, _ in trajectory]
    player_pi = [a for _, a in trajectory]

    # compute learner's policy
    logging.info('Computing policy with learned reward...')
    agent.setAttribute('rationality', AGENT_RATIONALITY)
    learner_pi = get_policy(agent, player_states, selection='distribution', threshold=PRUNE_THRESHOLD)

    logging.info('Computing evaluation metrics...')
    logging.info('Policy mismatch: {:.3f}'.format(policy_mismatch_prob(player_pi, learner_pi)))
    logging.info('Policy divergence: {:.3f}'.format(policy_divergence(player_pi, learner_pi)))

    logging.info('\nFinished!')
