import logging
import os
import random
import numpy as np
from psychsim.agent import Agent
from psychsim.world import World
from model_learning.metrics import evaluate_internal
from model_learning.planning import get_policy
from model_learning.util.plot import plot_bar
from model_learning.algorithms.max_entropy import MaxEntRewardLearning, THETA_STR
from model_learning.trajectory import sample_sub_trajectories
from model_learning.util.io import get_file_name_without_extension, create_clear_dir, save_object, change_log_handler, \
    load_object
from atomic.definitions.victims import Victims
from atomic.definitions.world_map import WorldMap
from atomic.definitions.map_utils import DEFAULT_MAPS
from atomic.parsing.replayer import Replayer
from atomic.parsing.parser import TrajectoryParser
from atomic.definitions.plotting import plot, plot_trajectories, plot_agent_location_frequencies, \
    plot_agent_action_frequencies, plot_location_frequencies, plot_action_frequencies
from atomic.model_learning.linear.rewards import create_reward_vector

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

AGENT_RATIONALITY = 1 / 0.1  # inverse temperature


class _Result(object):
    """
    Represents a result of reward model learning for a given player's data.
    """

    def __init__(self, file_name, trajectory, loc_freqs, action_freqs, metrics, stats, map_table):
        """
        Creates a new result.
        :param str file_name: the nam eof the log file containing the player's data.
        :param list[tuple[World, Distribution]] trajectory: the trajectory containing a list of state-action pairs.
        :param np.ndarray loc_freqs: the visitation frequencies for each location.
        :param dict[str, float] action_freqs: a dictionary containing the number of executions for each action.
        :param dict[str, float] metrics: a dictionary containing several internal evaluation metrics.
        :param dict[str, np.ndarray] stats: a dictionary with relevant statistics of the algorithm.
        :param dict map_table: a dictionary containing information on the environment map.
        """
        self.file_name = file_name
        self.trajectory = trajectory
        self.metrics = metrics
        self.stats = stats
        self.map_table = map_table
        self.loc_freqs = loc_freqs
        self.action_freqs = action_freqs


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
            maps = DEFAULT_MAPS
        super().__init__(replays, maps, {})

        self_all_replays = replays
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

    def process_files(self, num_steps=0, fname=None):
        # check results dir for each file, if results present, load them and don't reprocess
        files = []
        for file_name in self.files.copy():
            if not self._check_results(file_name):
                files.append(file_name)
        self.files = files

        if fname is None or fname in self.files:
            super().process_files(num_steps, fname)

    def _check_results(self, file_name):

        # checks already processed in this session
        if file_name in self.results:
            return True

        # checks if results file exists and tries to load it
        output_dir = os.path.join(self.output, get_file_name_without_extension(file_name))
        results_file = os.path.join(output_dir, 'result.pkl.gz')
        if os.path.isfile(results_file) and os.path.exists(results_file):
            try:
                self.results[file_name] = load_object(results_file)
                logging.info('Loaded valid results from {}'.format(results_file))
                return True
            except:
                return False

    def post_replay(self, parser, world, agent, observer, map_table,victims, world_map):
        """
        Performs linear reward model learning using the Maximum Entropy IRL algorithm.
        :param TrajectoryParser parser: the trajectory parser with the collected player trajectory.
        :param dict map_table: a dictionary containing information on the environment map.
        :param World world: the PsychSim world.
        :param Agent agent: the player agent.
        :param Agent observer: the observer / ASIST agent.
        :param WorldMap world_map: the world map with location and move actions information.
        :param Victims victims: the info about victims distribution over the world.
        :return:
        """
        # checks result data, ignore if exists
        if self._check_results(parser.filename):
            return

        # checks trajectory
        trajectory = parser.trajectory
        if len(trajectory) == 0:
            logging.info('Could not process datapoint, empty trajectory.')
            return

        # create output
        output_dir = os.path.join(self.output, get_file_name_without_extension(parser.filename))
        create_clear_dir(output_dir, self.clear)

        # sets up log to file
        change_log_handler(os.path.join(output_dir, 'learning.log'), self.verbosity)

        # sets general random seeds
        random.seed(self.seed)
        np.random.seed(self.seed)

        # print map
        neighbors = map_table['adjacency']
        locations = list(map_table['rooms'])
        coordinates = map_table['coordinates']
        plot(world, locations, neighbors, os.path.join(output_dir, 'env.{}'.format(self.img_format)), coordinates)

        logging.info('Parsed data file {} for player "{}" and got {} state-action pairs from {} events.'.format(
            parser.filename, parser.data['player_ID'].iloc[0], len(trajectory), parser.data.shape[0]))
        plot_trajectories(agent, locations, neighbors, [trajectory],
                          os.path.join(output_dir, 'trajectory.{}'.format(self.img_format)), coordinates,
                          title='Player Trajectory')
        loc_freqs = plot_agent_location_frequencies(
            agent, locations, os.path.join(output_dir, 'loc-frequencies.{}'.format(self.img_format)), [trajectory])
        action_freqs = plot_agent_action_frequencies(
            agent, os.path.join(output_dir, 'action-frequencies.{}'.format(self.img_format)), [trajectory])

        # collect sub-trajectories from player's trajectory
        trajectories = sample_sub_trajectories(trajectory, self.num_trajectories, self.length, seed=self.seed)
        logging.info('Collected {} trajectories of length {} from original trajectory.'.format(
            self.num_trajectories, self.length))
        plot_trajectories(agent, locations, neighbors, trajectories,
                          os.path.join(output_dir, 'sub-trajectories.{}'.format(self.img_format)), coordinates,
                          title='Training Sub-Trajectories')
        trajectories = [[(w.state, a) for w, a in t] for t in trajectories]

        # create reward vector and optimize reward weights via MaxEnt IRL
        logging.info('=================================')
        logging.info('Starting Maximum Entropy IRL optimization...')
        rwd_vector = create_reward_vector(agent, locations, world_map.moveActions[agent.name])
        alg = MaxEntRewardLearning(
            'max-ent', agent, rwd_vector, self.processes, self.normalize, self.learn_rate, self.epochs, self.diff, True,
            self.prune, self.horizon, self.seed)
        stats = alg.learn(trajectories, self.verbosity > 0)

        # saves results/stats
        alg.save_results(stats, output_dir, self.img_format)

        rwd_vector.set_rewards(agent, stats[THETA_STR])
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
        learner_pi = get_policy(agent, player_states, None, self.horizon, 'distribution', self.prune, self.processes)

        logging.info('Computing evaluation metrics...')
        metrics = evaluate_internal(player_pi, learner_pi)
        logging.info('Results:')
        for name, metric in metrics.items():
            logging.info('\t{}: {:.3f}'.format(name, metric))

        logging.info('Finished processing {}!'.format(parser.filename))
        logging.info('=================================\n\n')

        # saves and registers result
        result = _Result(parser.filename, trajectory, loc_freqs, action_freqs, metrics, stats, map_table)
        save_object(result, os.path.join(output_dir, 'result.pkl.gz'))
        self.results[parser.filename] = result

    def post_process(self):

        # create output
        output_dir = os.path.join(self.output, 'overall-results')
        create_clear_dir(output_dir, self.clear)

        # sets up log to file
        change_log_handler(os.path.join(output_dir, 'learning.log'), self.verbosity)

        logging.info('=================================')
        logging.info('Analyzing {} result datapoints, saving results in "{}"...'.format(len(self.results), output_dir))

        # separates results by map
        results = {}
        for result in self.results.values():
            map_name = result.map_table['name']
            if map_name not in results:
                results[map_name] = []
            results[map_name].append(result)

        # saves results for each map
        for map_name, map_results in results.items():
            map_table = map_results[0].map_table
            locations = list(map_table['rooms'])

            # saves location frequencies
            loc_data = np.sum([result.loc_freqs for result in map_results], axis=0)
            plot_location_frequencies(
                loc_data, locations,
                os.path.join(output_dir, '{}-loc-frequencies.{}'.format(map_name, self.img_format)),
                '{} Location Visitation Frequencies'.format(map_name))

            # saves action frequencies
            action_data = {}
            for result in map_results:
                action_data.update(result.action_freqs)
            plot_action_frequencies(
                action_data, os.path.join(output_dir, '{}-action-frequencies.{}'.format(map_name, self.img_format)),
                '{} Action Execution Frequencies'.format(map_name))

        # overall metrics
        metrics = {}
        for file_name, result in self.results.items():
            for name, metric in result.metrics.items():
                if name not in metrics:
                    metrics[name] = {}
                metrics[name][get_file_name_without_extension(file_name)] = metric

        logging.info('Reward model learning metrics:')
        for name, metric_values in metrics.items():
            logging.info('\t{}: {:.3f}'.format(name, np.mean(list(metric_values.values()))))
            plot_bar(metric_values, 'Overall {}'.format(name.title()), None,
                     os.path.join(output_dir, 'metric-{}.{}'.format(name.lower().replace(' ', '-'), self.img_format)),
                     True, 'Participant', name)
