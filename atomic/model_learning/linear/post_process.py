import csv
import logging
import os
import numpy as np
import matplotlib.pyplot as plt
from collections import OrderedDict
from sklearn.cluster import AgglomerativeClustering
from scipy.cluster.hierarchy import dendrogram
from model_learning.algorithms.max_entropy import THETA_STR
from model_learning.metrics import evaluate_internal
from model_learning.planning import get_policy
from model_learning.util.plot import plot_bar, format_and_save_plot
from atomic.definitions.world_map import WorldMap
from atomic.definitions.plotting import plot_location_frequencies, plot_action_frequencies, plot_trajectories
from atomic.model_learning.linear.rewards import create_reward_vector
from atomic.model_learning.stats import get_location_frequencies, get_action_frequencies
from atomic.parsing.parser import DataParser
from atomic.model_learning.linear.analyzer import RewardModelAnalyzer

__author__ = 'Pedro Sequeira'
__email__ = 'pedrodbs@gmail.com'

DEF_DIST_THRESHOLD = .6
DEF_LINKAGE = 'ward'

AGENT_RATIONALITY = 1 / 0.1  # inverse temperature


class PostProcessor(object):

    def __init__(self, analyzer, linkage='ward', dist_threshold=DEF_DIST_THRESHOLD):
        """
        Creates a new post-processor for the given analyzer.
        :param RewardModelAnalyzer analyzer: the reward model analyzer containing the necessary data.
        :param str linkage: the clustering linkage criterion.
        :param float dist_threshold: the distance above which clusters are not merged.
        """
        self.analyzer = analyzer
        self.linkage = linkage
        self.dist_threshold = dist_threshold

        logging.info('=================================')
        if self.analyzer.results is None or len(self.analyzer.results) == 0 or \
                self.analyzer.trajectories is None or len(self.analyzer.trajectories) == 0:
            logging.warning('Inexistent or incomplete results!')
            return

        # loads parsers corresponding to each result
        logging.info('Loading players\' log data...')
        self.file_names = []
        self.parsers = {}
        self.agents = {}
        map_name = None
        map_table = None
        for filename in self.analyzer.results:
            # check file, skip if necessary
            logging.info('Loading log file {}...'.format(filename))
            if not os.path.isfile(filename) or not os.path.exists(filename):
                logging.warning('Skipping "{}", could not find log file to parse!'.format(filename))
                continue

            # check equal map, skip if necessary
            parser = DataParser(filename)
            _map_name, map_table = self.analyzer.get_map(parser, logging)
            if map_name is not None and map_name != _map_name:
                logging.warning('Got data for a different map: {} (only considering {})'.format(_map_name, map_name))
                continue

            # retrieve agent from trajectory, skip if necessary
            trajectory = self.analyzer.trajectories[filename]
            if parser.player_name() not in trajectory[-1][0].agents:
                logging.warning('Skipping "{}", could not find agent "{}"!'.format(filename, parser.player_name()))
                continue

            map_name = _map_name
            self.file_names.append(filename)
            self.parsers[filename] = parser
            self.agents[filename] = trajectory[-1][0].agents[parser.player_name()]

        self.locations = list(map_table['rooms'])

    def process_reward_weights(self, output_dir):
        logging.info('\n=================================')
        logging.info('Analyzing models\' reward weights for {} results...'.format(len(self.file_names)))

        # gathers all reward weights
        thetas = []
        player_names = []
        agent = next(iter(self.agents.values()))
        rwd_feat_names = create_reward_vector(agent, self.locations, WorldMap.get_move_actions(agent)).names
        for filename in self.file_names:
            result = self.analyzer.results[filename]
            thetas.append(result.stats[THETA_STR])
            player_names.append(self.parsers[filename].player_name())
        thetas = np.array(thetas)

        # overall weight mean
        data = np.array([np.mean(thetas, axis=0), np.std(thetas, axis=0) / len(thetas)]).T.tolist()
        plot_bar(OrderedDict(zip(rwd_feat_names, data)),
                 'Overall Mean Weights', os.path.join(output_dir, 'weights-mean.{}'.format(self.analyzer.img_format)),
                 plot_mean=False)

        # performs clustering of reward weights
        clustering = AgglomerativeClustering(
            n_clusters=None, linkage=self.linkage, distance_threshold=self.dist_threshold)
        clustering.fit(thetas)

        # gets clusters
        clusters = {}
        for idx, cluster in enumerate(clustering.labels_):
            if cluster not in clusters:
                clusters[cluster] = []
            clusters[cluster].append(idx)

        # mean weights within each cluster
        logging.info('Found {} clusters:'.format(clustering.n_clusters_))
        for cluster, idxs in clusters.items():
            logging.info('\tCluster {}: {}'.format(cluster, idxs))
            data = np.array([np.mean(thetas[idxs], axis=0), np.std(thetas[idxs], axis=0) / len(idxs)]).T.tolist()
            plot_bar(OrderedDict(zip(rwd_feat_names, data)),
                     'Mean Weights for Cluster {}'.format(cluster),
                     os.path.join(output_dir, 'weights-mean-{}.{}'.format(cluster, self.analyzer.img_format)),
                     plot_mean=False)

        with open(os.path.join(output_dir, 'clusters.csv'), 'w') as f:
            write = csv.writer(f)
            write.writerow(['Cluster', 'Filename'])
            write.writerows(list(zip(clustering.labels_, self.file_names)))

        # dendrogram
        linkage_matrix = self.get_linkage_matrix(clustering)
        dendrogram(linkage_matrix, clustering.n_clusters_, 'level', labels=player_names,
                   leaf_rotation=45, leaf_font_size=8)
        plt.axhline(y=self.dist_threshold, c='red', ls='--', lw=0.6)
        format_and_save_plot(plt.gca(), 'Reward Weights Clustering Dendrogram',
                             os.path.join(output_dir, 'weights-dendrogram.{}'.format(self.analyzer.img_format)),
                             show_legend=False)

        # distances plot
        plt.figure()
        plt.plot(np.hstack(([0], clustering.distances_)))
        plt.xlim([0, len(clustering.distances_)])
        plt.ylim(ymin=0)
        plt.xticks(np.arange(len(clustering.distances_) + 1), np.flip(np.arange(len(clustering.distances_) + 1) + 1))
        plt.axvline(x=len(clustering.distances_) - clustering.n_clusters_ + 1, c='red', ls='--', lw=0.6)
        format_and_save_plot(plt.gca(), 'Reward Weights Clustering Distance',
                             os.path.join(output_dir, 'weights-distance.{}'.format(self.analyzer.img_format)),
                             x_label='Num. Clusters', show_legend=False)

    @staticmethod
    def get_linkage_matrix(model):
        """
        Plots a dendrogram from the `sklearn` clustering model.
        See: https://scikit-learn.org/stable/auto_examples/cluster/plot_agglomerative_dendrogram.html
        :param AgglomerativeClustering model: the clustering model.
        :return:
        """
        # create the counts of samples under each node
        counts = np.zeros(model.children_.shape[0])
        n_samples = len(model.labels_)
        for i, merge in enumerate(model.children_):
            current_count = 0
            for child_idx in merge:
                if child_idx < n_samples:
                    current_count += 1  # leaf node
                else:
                    current_count += counts[child_idx - n_samples]
            counts[i] = current_count

        return np.column_stack([model.children_, model.distances_, counts]).astype(float)

    def process_player_data(self, output_dir):
        logging.info('\n=================================')
        logging.info('Analyzing mean player behavior for {} results...'.format(len(self.file_names)))

        trajectories = []
        traj_agents = []
        loc_data = []
        action_data = []
        all_actions = set()
        map_table = None

        # gathers stats about locations visited and actions executed
        for filename in self.file_names:
            trajectory = self.analyzer.trajectories[filename]
            trajectories.append(trajectory)

            parser = self.parsers[filename]
            _, map_table = self.analyzer.get_map(parser, logging)

            agent = self.agents[filename]
            traj_agents.append(agent)
            loc_data.append(get_location_frequencies(agent, [trajectory], self.locations))
            act_freqs = get_action_frequencies(agent, [trajectory])
            act_freqs = OrderedDict(
                {str(a).replace('{}-'.format(agent.name), '').replace('_', ' '): val for a, val in act_freqs.items()})
            action_data.append(act_freqs)
            all_actions.update(action_data[-1].keys())

        all_actions = sorted(all_actions)

        # saves mean location and action frequencies
        loc_data = {loc: [np.mean([loc_freqs[loc] for loc_freqs in loc_data]),
                          np.std([loc_freqs[loc] for loc_freqs in loc_data]) / len(loc_data)]
                    for loc in self.locations}
        plot_location_frequencies(loc_data,
                                  os.path.join(output_dir, 'loc-frequencies.{}'.format(self.analyzer.img_format)),
                                  'Mean Location Visitation Frequencies')

        action_data = {act: [np.mean([act_freqs[act] for act_freqs in action_data]),
                             np.std([act_freqs[act] for act_freqs in action_data]) / len(action_data)]
                       for act in all_actions}
        plot_action_frequencies(action_data,
                                os.path.join(output_dir, 'action-frequencies.{}'.format(self.analyzer.img_format)),
                                'Mean Action Execution Frequencies')

        # saves all player trajectories
        plot_trajectories(traj_agents, trajectories, self.locations, map_table['adjacency'],
                          os.path.join(output_dir, 'trajectories.{}'.format(self.analyzer.img_format)),
                          map_table['coordinates'], title='Player Trajectories')

        # saves trajectory length
        traj_len_data = OrderedDict({self.parsers[filename].player_name(): len(self.analyzer.trajectories[filename])
                                     for filename in self.file_names})
        plot_bar(traj_len_data, 'Player Trajectory Length',
                 os.path.join(output_dir, 'trajectory-length.{}'.format(self.analyzer.img_format)))

    def process_evaluation_metrics(self, output_dir):
        logging.info('\n=================================')
        logging.info('Calculating evaluation metrics for {} results...'.format(len(self.file_names)))

        metrics_data = {}
        for filename in self.file_names:
            parser = self.parsers[filename]
            agent = self.agents[filename]
            trajectory = self.analyzer.trajectories[filename]
            result = self.analyzer.results[filename]

            # player's observed "policy"
            player_states = [w.state for w, _ in trajectory]
            player_pi = [a for _, a in trajectory]

            # compute learner's policy
            rwd_vector = create_reward_vector(agent, self.locations, WorldMap.get_move_actions(agent))
            rwd_vector.set_rewards(agent, result.stats[THETA_STR])
            logging.info('Computing policy with learned reward for {} states...'.format(len(player_states)))
            agent.setAttribute('rationality', AGENT_RATIONALITY)
            learner_pi = get_policy(agent, player_states, None, self.analyzer.horizon, 'distribution',
                                    self.analyzer.prune, self.analyzer.processes)

            # gets algorithm internal performance metrics
            metrics = evaluate_internal(player_pi, learner_pi)
            for metric_name, metric in metrics.items():
                if metric_name not in metrics_data:
                    metrics_data[metric_name] = {}
                metrics_data[metric_name][parser.player_name()] = metric

        for metric_name, metric_values in metrics_data.items():
            plot_bar(metric_values, metric_name.title(), os.path.join(output_dir, 'metric-{}.{}'.format(
                metric_name.lower().replace(' ', '-'), self.analyzer.img_format)), None, y_label=metric_name)
