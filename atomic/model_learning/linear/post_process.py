import logging
import os
import numpy as np
from collections import OrderedDict
from model_learning.algorithms.max_entropy import THETA_STR
from model_learning.metrics import evaluate_internal
from model_learning.planning import get_policy
from model_learning.util.io import create_clear_dir, change_log_handler
from model_learning.util.plot import plot_bar
from atomic.definitions.plotting import plot_location_frequencies, plot_action_frequencies
from atomic.model_learning.linear.rewards import create_reward_vector
from atomic.model_learning.stats import get_location_frequencies, get_action_frequencies
from atomic.parsing.parser import DataParser
from atomic.scenarios.single_player import make_single_player_world
from atomic.model_learning.linear.analyzer import RewardModelAnalyzer

__author__ = 'Pedro Sequeira'
__email__ = 'pedrodbs@gmail.com'

AGENT_RATIONALITY = 1 / 0.1  # inverse temperature


class PostProcessor(object):

    def __init__(self, analyzer):
        """
        Creates a new post-processor for the given analyzer.
        :param RewardModelAnalyzer analyzer: the reward model analyzer containing the necessary data.
        """
        self.analyzer = analyzer

    def run(self):
        """
        Runs the post-processor over the collected results.
        """

        logging.info('=================================')
        if self.analyzer.results is None or len(self.analyzer.results) == 0 or \
                self.analyzer.trajectories is None or len(self.analyzer.trajectories) == 0:
            logging.warning('Inexistent or incomplete results!')
            return

        # create output and log
        output_dir = os.path.join(self.analyzer.output, 'post-process')
        create_clear_dir(output_dir, self.analyzer.clear)
        change_log_handler(os.path.join(output_dir, 'learning.log'), self.analyzer.verbosity)

        # loads parsers corresponding to each result
        logging.info('Loading players\' log data...')
        info = {}
        map_name = None
        map_table = None
        file_names = []
        for filename in self.analyzer.results:
            # check file, skip if necessary
            if not os.path.isfile(filename) or not os.path.exists(filename):
                logging.warning('Skipping "{}", could not find log file to parse!'.format(filename))
                continue

            # check equal map, skip if necessary
            parser = DataParser(filename)
            _map_name, map_table = self.analyzer.get_map(parser, logging)
            if map_name is not None and map_name != _map_name:
                logging.warning('Got data for a different map: {} (only considering {})'.format(_map_name, map_name))
                continue
            map_name = _map_name
            file_names.append(filename)

            world, agent, observer, victims, world_map = \
                make_single_player_world(parser.player_name(), map_table['start'],
                                         map_table['adjacency'], map_table['victims'], False, True)

            info[filename] = (parser, agent, world_map)

        locations = list(map_table['rooms'])

        # performs different post-processing
        logging.info('Analyzing {} results, saving post-process results in "{}"...'.format(
            len(self.analyzer.results), output_dir))
        self._process_player_data(output_dir, locations, file_names, info)
        self._process_evaluation_metrics(output_dir, locations, file_names, info)

    def _process_player_data(self, output_dir, locations, file_names, info):

        logging.info('Analyzing mean player behavior {} for results...'.format(len(file_names), output_dir))

        loc_data = []
        action_data = []
        all_actions = set()

        # gathers stats about locations visited and actions executed
        for filename in file_names:
            _, agent, _ = info[filename]
            loc_data.append(get_location_frequencies(agent, [self.analyzer.trajectories[filename]], locations))
            act_freqs = get_action_frequencies(agent, [self.analyzer.trajectories[filename]])
            act_freqs = OrderedDict(
                {str(a).replace('{}-'.format(agent.name), '').replace('_', ' '): val for a, val in act_freqs.items()})
            action_data.append(act_freqs)
            all_actions.update(action_data[-1].keys())

        # saves location and action frequencies
        loc_data = {loc: np.mean([loc_freqs[loc] for loc_freqs in loc_data]) for loc in locations}
        plot_location_frequencies(loc_data,
                                  os.path.join(output_dir, 'loc-frequencies.{}'.format(self.analyzer.img_format)),
                                  'Mean Location Visitation Frequencies')

        action_data = {act: np.mean([act_freqs[act] for act_freqs in action_data]) for act in all_actions}
        plot_action_frequencies(action_data,
                                os.path.join(output_dir, 'action-frequencies.{}'.format(self.analyzer.img_format)),
                                'Mean Action Execution Frequencies')

    def _process_evaluation_metrics(self, output_dir, locations, file_names, info):
        logging.info('Calculating evaluation metrics for results...'.format(len(file_names), output_dir))

        metrics_data = {}
        for filename in file_names:
            parser, agent, world_map = info[filename]
            trajectory = self.analyzer.trajectories[filename]
            result = self.analyzer.results[filename]

            # player's observed "policy"
            player_states = [w.state for w, _ in trajectory]
            player_pi = [a for _, a in trajectory]

            # compute learner's policy
            rwd_vector = create_reward_vector(agent, locations, world_map.moveActions[agent.name])
            rwd_vector.set_rewards(agent, result.stats[THETA_STR])
            logging.info('Computing policy with learned reward for {} states...'.format(len(player_states)))
            agent.setAttribute('rationality', AGENT_RATIONALITY)
            learner_pi = get_policy(agent, player_states, None, self.analyzer.horizon, 'distribution',
                                    self.analyzer.prune, self.analyzer.processes)

            # gets algorithm internal performance metrics
            metrics = evaluate_internal(player_pi, learner_pi)
            for metric_name, metric in metrics:
                if metric_name not in metrics_data:
                    metrics_data[metric_name] = {}
                metrics_data[metric_name][parser.player_name()] = metric

        for metric_name, metric_values in metrics_data.items():
            plot_bar(metric_values, metric_name.title(), None,
                     os.path.join(output_dir, 'metric-{}.{}'.format(
                         metric_name.lower().replace(' ', '-'), self.analyzer.img_format)),
                     True, '', metric_name, False)
