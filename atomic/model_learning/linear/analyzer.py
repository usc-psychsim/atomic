import logging
import os
import copy
import random
import numpy as np
from collections import OrderedDict

from atomic.definitions.features import get_mission_seconds_key
from model_learning.util.plot import plot_bar
from model_learning.algorithms.max_entropy import MaxEntRewardLearning, THETA_STR
from model_learning.trajectory import sample_spread_sub_trajectories
from model_learning.util.io import get_file_name_without_extension, create_clear_dir, save_object, change_log_handler, \
    load_object
from atomic.parsing.replayer import Replayer, SUBJECT_ID_TAG, COND_MAP_TAG
from atomic.definitions import victims
from atomic.definitions.map_utils import get_default_maps
from atomic.definitions.plotting import plot_environment, plot_trajectories, plot_agent_location_frequencies, \
    plot_agent_action_frequencies
from atomic.model_learning.linear.rewards import create_reward_vector
from atomic.model_learning.parser import TrajectoryParser

__author__ = 'Pedro Sequeira'
__email__ = 'pedrodbs@gmail.com'

# trajectory params
NUM_TRAJECTORIES = os.cpu_count()  # 8 # 20
TRAJ_LENGTH = 10  # 15
PRUNE_THRESHOLD = 5e-2  # 1e-2
SEED = 0

# learning algorithm params
HORIZON = 2
NORM_THETA = True
LEARNING_RATE = 0.5  # 1e-2
MAX_EPOCHS = 40  # 100  # 200
DIFF_THRESHOLD = 5e-3  # 1e-3

# data params
OUTPUT_DIR = 'output/linear-reward-learning'
PROCESSES = None
IMG_FORMAT = 'pdf'  # 'png'
TRAJECTORY_FILE_NAME = 'trajectory.pkl.gz'
RESULTS_FILE_NAME = 'result.pkl.gz'

AGENT_RATIONALITY = 1 / 0.1  # inverse temperature


class RewardModelAnalyzer(Replayer):
    """
    Replay analyzer that performs linear reward model learning given a player's data using the MaxEnt IRL algorithm.
    """
    parser_class = TrajectoryParser

    def __init__(self, replays, output=OUTPUT_DIR, maps=None, clear=True,
                 num_trajectories=NUM_TRAJECTORIES, length=TRAJ_LENGTH,
                 normalize=NORM_THETA, learn_rate=LEARNING_RATE, epochs=MAX_EPOCHS,
                 diff=DIFF_THRESHOLD, prune=PRUNE_THRESHOLD, horizon=HORIZON,
                 seed=0, verbosity=0, processes=PROCESSES, img_format=IMG_FORMAT):
        """
        Creates a new reward model learning replayer.
        :param list[str] replays: list of replay log files to process containing the player data.
        :param str output: path to the directory in which to save results.
        :param dict[str,dict[str,str]] maps: the map configuration dictionary.
        :param bool clear: whether to clear the output sub-directories.
        :param int num_trajectories: number of trajectories to use for reward learning.
        :param int length: length of the sub-trajectories used for reward learning.
        :param bool normalize: whether to normalize reward weights at each step of the algorithm.
        :param float learn_rate: the gradient descent learning/update rate.
        :param int epochs: the maximum number of gradient descent steps.
        :param float diff: the termination threshold for the weight vector difference.
        :param float prune: the likelihood below which stochastic outcomes are pruned.
        :param int horizon: planning horizon of the "learner" agent.
        :param int seed: seed for random number generation.
        :param int verbosity: verbosity level.
        :param int processes: the number of processes/cores to use. If `None`, all available cores will be used.
        :param str img_format: the format/extension of result images to be saved.
        """
        if maps is None:
            maps = get_default_maps()
        super().__init__(replays, maps, {}, create_observer=False)

        self._all_replays = replays
        self.output = output
        self.clear = clear
        self.num_trajectories = num_trajectories
        self.length = length
        self.normalize = normalize
        self.learn_rate = learn_rate
        self.epochs = epochs
        self.diff = diff
        self.prune = prune
        self.horizon = horizon
        self.seed = seed
        self.verbosity = verbosity
        self.processes = processes
        self.img_format = img_format

        self.results = {}
        self.trajectories = {}
        self.agent_names = {}
        self.map_tables = {}
        self.trial_conditions = {}

        self._output_dir = None

    def _check_results(self):

        # checks already processed in this session
        if self.file_name in self.results and self.file_name in self.trajectories and \
                self.file_name in self.map_tables and self.file_name in self.agent_names:
            return True

        # checks if results file exists and tries to load it
        output_dir = os.path.join(self.output, get_file_name_without_extension(self.file_name))
        results_file = os.path.join(output_dir, RESULTS_FILE_NAME)
        trajectory_file = os.path.join(output_dir, TRAJECTORY_FILE_NAME)
        if os.path.isfile(results_file) and os.path.exists(results_file) and \
                os.path.isfile(trajectory_file) and os.path.exists(trajectory_file):
            try:
                result = load_object(results_file)
                logging.info('Loaded valid results from {}'.format(results_file))
                trajectory = load_object(trajectory_file)
                logging.info('Loaded valid trajectory from {}'.format(trajectory_file))
                self._register_results(
                    self.file_name, trajectory, result, self.parser.player_name(), self.map_table, self.conditions)
                return True
            except:
                return False

    def _register_results(self, file_name, trajectory, results, agent_name, map_table, conditions):
        self.trajectories[file_name] = trajectory
        self.results[file_name] = results
        self.agent_names[file_name] = agent_name
        self.map_tables[file_name] = map_table
        self.trial_conditions[file_name] = copy.deepcopy(conditions)

    def pre_replay(self, logger=logging):
        # check results and avoids creating stuff
        return False if self._check_results() else super().pre_replay(logger)

    def replay(self, duration, logger):
        # checks results and avoids replaying episode
        if self._check_results():
            return

        # create output
        self._output_dir = os.path.join(self.output, get_file_name_without_extension(self.parser.filename))
        create_clear_dir(self._output_dir, self.clear)

        # sets up log to file
        change_log_handler(os.path.join(self._output_dir, 'learning.log'), self.verbosity)

        # replays trajectory
        super().replay(duration, logger)

    def get_player_name(self, filename):
        # get player name if possible from the conditions dict
        conditions = self.trial_conditions[filename]
        if SUBJECT_ID_TAG in conditions and COND_MAP_TAG in conditions:
            return '{}-{}'.format(conditions[SUBJECT_ID_TAG], conditions[COND_MAP_TAG][0])
        return self.agent_names[filename]

    def post_replay(self):
        """
        Performs linear reward model learning using the Maximum Entropy IRL algorithm.
        """
        # checks result and avoids performing IRL
        if self._check_results():
            return

        # checks trajectory
        trajectory = self.parser.trajectory
        if len(trajectory) <= self.length + self.num_trajectories - 1:
            logging.info('Could not process datapoint, empty or very short trajectory: {}'.format(
                self.parser.filename))
            return

        # todo hack
        prob_no_beep = victims.PROB_NO_BEEP
        victims.PROB_NO_BEEP = 0

        # delete observer if present (not needed)
        if self.observer is not None:
            del self.world.agents[self.observer.name]
            logging.info('Removed observer agent from PsychSim world.')

        # sets general random seeds
        random.seed(self.seed)
        np.random.seed(self.seed)

        neighbors = self.map_table.adjacency
        locations = self.map_table.rooms_list
        coordinates = self.map_table.coordinates

        # print map
        plot_environment(self.world, locations, neighbors,
                         os.path.join(self._output_dir, 'env.{}'.format(self.img_format)), coordinates)

        self.plot_player_data(coordinates, locations, neighbors, trajectory)

        trajectories = self.collect_sub_trajectories(coordinates, locations, neighbors, trajectory)

        # create reward vector and optimize reward weights via MaxEnt IRL
        logging.info('=================================')
        logging.info('Starting Maximum Entropy IRL optimization using {} processes...'.format(
            os.cpu_count() if self.processes is None else self.processes))
        rwd_vector = create_reward_vector(
            self.triage_agent, locations, self.world_map.moveActions[self.triage_agent.name])

        alg = MaxEntRewardLearning(
            'max-ent', self.triage_agent.name, rwd_vector, self.processes, self.normalize, self.learn_rate, self.epochs,
            self.diff, True, self.prune, self.horizon, self.seed)
        result = alg.learn(trajectories, self.parser.filename, self.verbosity > 0)

        self.save_results(alg, result, rwd_vector, trajectory)

        logging.info('Finished processing {}!'.format(self.parser.filename))
        logging.info('=================================\n\n')

        # todo hack
        victims.PROB_NO_BEEP = prob_no_beep

    def plot_player_data(self, coordinates, locations, neighbors, trajectory):

        # print trajectories and player data
        logging.info('Parsed data file {} for player "{}" and got {} state-action pairs from {} events.'.format(
            self.parser.filename, self.parser.player_name(), len(trajectory), self.parser.data.shape[0]))
        plot_trajectories(
            self.triage_agent, [trajectory], locations, neighbors,
            os.path.join(self._output_dir, 'trajectory.{}'.format(self.img_format)), coordinates,
            title='Player Trajectory')
        plot_agent_location_frequencies(
            self.triage_agent, [trajectory], locations,
            os.path.join(self._output_dir, 'loc-frequencies.{}'.format(self.img_format)))
        plot_agent_action_frequencies(
            self.triage_agent, [trajectory],
            os.path.join(self._output_dir, 'action-frequencies.{}'.format(self.img_format)))

    def collect_sub_trajectories(self, coordinates, locations, neighbors, trajectory):
        # only consider first half of mission
        idx = 0
        for idx in range(len(trajectory)):
            secs = trajectory[idx][0].getFeature(get_mission_seconds_key(), unique=True)
            if secs >= 5 * 60:
                break

        # collect sub-trajectories from player's trajectory
        trajectories = sample_spread_sub_trajectories(trajectory[:idx], self.num_trajectories, self.length)

        logging.info('Collected {} trajectories of length {} from original trajectory (length {}).'.format(
            self.num_trajectories, self.length, idx + 1))
        plot_trajectories(self.triage_agent, trajectories, locations, neighbors,
                          os.path.join(self._output_dir, 'sub-trajectories.{}'.format(self.img_format)), coordinates,
                          title='Training Sub-Trajectories')

        return trajectories

    def save_results(self, alg, result, rwd_vector, trajectory):

        # saves results/stats
        alg.save_results(result, self._output_dir, self.img_format)
        save_object(result, os.path.join(self._output_dir, RESULTS_FILE_NAME))
        save_object(trajectory, os.path.join(self._output_dir, TRAJECTORY_FILE_NAME))
        self._register_results(
            self.file_name, trajectory, result, self.parser.player_name(), self.map_table, self.conditions)

        logging.info('=================================')

        # gets optimal reward function
        rwd_weights = result.stats[THETA_STR]
        rwd_vector.set_rewards(self.triage_agent, rwd_weights)
        with np.printoptions(precision=2, suppress=True):
            logging.info('Optimized reward weights: {}'.format(rwd_weights))
        plot_bar(OrderedDict(zip(rwd_vector.names, rwd_weights)), 'Optimal Reward Weights $θ^*$',
                 os.path.join(self._output_dir, 'learner-theta.{}'.format(self.img_format)), plot_mean=False)
