import logging
import os
import numpy as np
from collections import OrderedDict
from model_learning.algorithms.max_entropy import THETA_STR
from model_learning.clustering.linear import cluster_linear_rewards, get_clusters_means, save_mean_cluster_weights, \
    save_clusters_info, plot_clustering_distances, plot_clustering_dendrogram
from model_learning.evaluation.linear import cross_evaluation
from model_learning.util.plot import plot_bar, plot_confusion_matrix
from atomic.definitions.world_map import WorldMap
from atomic.definitions.plotting import plot_location_frequencies, plot_action_frequencies, plot_trajectories
from atomic.model_learning.linear.rewards import create_reward_vector
from atomic.model_learning.stats import get_location_frequencies, get_action_frequencies
from atomic.model_learning.linear.analyzer import RewardModelAnalyzer

__author__ = 'Pedro Sequeira'
__email__ = 'pedrodbs@gmail.com'

DEF_DIST_THRESHOLD = .6
DEF_LINKAGE = 'ward'

CONF_MAT_COLOR_MAP = 'inferno'

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

        logging.info('Post-processing IRL data for the following files:')
        for filename in self.analyzer.results:
            logging.info('\t{}, player: "{}", map: "{}", {} steps'.format(
                filename, self.analyzer.player_names[filename],
                self.analyzer.map_tables[filename]['name'], len(self.analyzer.trajectories[filename])))

    def process_reward_weights(self, output_dir):

        file_names = list(self.analyzer.results)
        logging.info('\n=================================')
        logging.info('Analyzing models\' reward weights for {} results...'.format(len(file_names)))

        # performs cluster of reward weights
        results = [self.analyzer.results[filename] for filename in file_names]
        clustering, thetas = cluster_linear_rewards(results, self.linkage, self.dist_threshold)

        # gets rwd feature names with dummy info
        player_name = self.analyzer.player_names[file_names[0]]
        agent = self.analyzer.trajectories[file_names[0]][-1][0].agents[player_name]
        locations = self.analyzer.map_tables[file_names[0]]['rooms']
        rwd_feat_names = create_reward_vector(agent, locations, WorldMap.get_move_actions(agent)).names

        # overall weight mean
        data = np.array([np.mean(thetas, axis=0), np.std(thetas, axis=0) / len(thetas)]).T.tolist()
        plot_bar(OrderedDict(zip(rwd_feat_names, data)),
                 'Overall Mean Weights', os.path.join(output_dir, 'weights-mean.{}'.format(self.analyzer.img_format)),
                 plot_mean=False)

        # mean weights within each cluster
        clusters, cluster_weights = get_clusters_means(clustering, thetas)
        logging.info('Found {} clusters:'.format(clustering.n_clusters_))
        for cluster in sorted(cluster_weights):
            idxs = clusters[cluster]
            logging.info('\tCluster {}: {}'.format(cluster, idxs))
            data = cluster_weights[cluster]
            data[1] = data[1] / len(idxs)
            plot_bar(OrderedDict(zip(rwd_feat_names, data.T.tolist())),
                     'Mean Weights for Cluster {}'.format(cluster),
                     os.path.join(output_dir, 'weights-mean-{}.{}'.format(cluster, self.analyzer.img_format)),
                     plot_mean=False)

        player_names = [self.analyzer.player_names[filename] for filename in file_names]
        save_mean_cluster_weights(cluster_weights, os.path.join(output_dir, 'cluster-weights.csv'), rwd_feat_names)
        save_clusters_info(clustering, OrderedDict({'Player name': player_names, 'Filename': file_names}),
                           thetas, os.path.join(output_dir, 'clusters.csv'), rwd_feat_names)

        # dendrogram
        plot_clustering_dendrogram(
            clustering, os.path.join(output_dir, 'weights-dendrogram.{}'.format(self.analyzer.img_format)),
            player_names)

        plot_clustering_distances(
            clustering, os.path.join(output_dir, 'weights-distance.{}'.format(self.analyzer.img_format)))

    def process_player_data(self, output_dir):

        file_names = list(self.analyzer.results)
        logging.info('\n=================================')
        logging.info('Analyzing mean player behavior for {} results...'.format(len(file_names)))

        # separates stats by map name
        trajectories = {}
        traj_agents = {}
        location_data = {}
        action_data = {}
        map_tables = {}
        all_actions = set()

        # gathers stats about locations visited and actions executed
        for filename in file_names:
            map_table = self.analyzer.map_tables[filename]
            map_name = map_table['name'].lower()
            if map_name not in trajectories:
                map_tables[map_name] = map_table
                trajectories[map_name] = []
                traj_agents[map_name] = []
                location_data[map_name] = []
                action_data[map_name] = []

            trajectory = self.analyzer.trajectories[filename]
            trajectories[map_name].append(trajectory)

            agent = trajectory[-1][0].agents[self.analyzer.player_names[filename]]
            traj_agents[map_name].append(agent)

            location_data[map_name].append(get_location_frequencies(agent, [trajectory], map_table['rooms']))

            act_freqs = get_action_frequencies(agent, [trajectory])
            act_freqs = OrderedDict(
                {str(a).replace('{}-'.format(agent.name), '').replace('_', ' '): val for a, val in act_freqs.items()})
            action_data[map_name].append(act_freqs)

            all_actions.update(act_freqs.keys())

        all_actions = sorted(all_actions)

        for map_name, map_table in map_tables.items():
            # saves mean location and action frequencies
            locations = list(map_table['rooms'])
            loc_data = {loc: [np.mean([loc_freqs[loc] for loc_freqs in location_data[map_name]]),
                              np.std([loc_freqs[loc] for loc_freqs in location_data[map_name]]) /
                              len(location_data[map_name])]
                        for loc in locations}
            plot_location_frequencies(
                loc_data, os.path.join(output_dir, '{}-loc-frequencies.{}'.format(map_name, self.analyzer.img_format)),
                'Mean Location Visitation Frequencies')

            act_data = action_data[map_name]
            act_data = {act: [np.mean([act_freqs[act] for act_freqs in act_data]),
                              np.std([act_freqs[act] for act_freqs in act_data]) / len(act_data)]
                        for act in all_actions}
            plot_action_frequencies(
                act_data,
                os.path.join(output_dir, '{}-action-frequencies.{}'.format(map_name, self.analyzer.img_format)),
                'Mean Action Execution Frequencies')

            # saves all player trajectories
            plot_trajectories(traj_agents[map_name], trajectories[map_name], locations, map_table['adjacency'],
                              os.path.join(output_dir, '{}-trajectories.{}'.format(map_name, self.analyzer.img_format)),
                              map_table['coordinates'], title='Player Trajectories')

            # saves trajectory length
            traj_len_data = OrderedDict(
                {self.analyzer.player_names[filename]: len(self.analyzer.trajectories[filename])
                 for filename in file_names})
            plot_bar(traj_len_data, 'Player Trajectory Length',
                     os.path.join(output_dir, '{}-trajectory-length.{}'.format(map_name, self.analyzer.img_format)))

    def process_evaluation(self, output_dir):

        file_names = list(self.analyzer.results)
        logging.info('\n=================================')
        logging.info('Performing cross-evaluation of reward functions for {} results...'.format(len(file_names)))

        # calculates eval metrics for each agent if using their own and others' rwd vectors
        trajectories = [self.analyzer.trajectories[filename] for filename in file_names]
        player_names = [self.analyzer.player_names[filename] for filename in file_names]
        agents = [trajectories[i][-1][0].agents[player_names[i]] for i in range(len(trajectories))]
        map_locs = [list(self.analyzer.map_tables[filename]['rooms']) for filename in file_names]
        rwd_vectors = [create_reward_vector(agents[i], map_locs[i], WorldMap.get_move_actions(agents[i]))
                       for i in range(len(agents))]
        rwd_weights = [self.analyzer.results[filename].stats[THETA_STR] for filename in file_names]

        eval_matrix = cross_evaluation(
            trajectories, player_names, rwd_vectors, rwd_weights, True,
            AGENT_RATIONALITY, self.analyzer.horizon, self.analyzer.prune, self.analyzer.processes)

        # gets internal evaluation (each agent against its own expert's reward function)
        for metric_name, matrix in eval_matrix.items():
            metric_values = {}
            for i, filename in enumerate(file_names):
                player_name = self.analyzer.player_names[filename]
                metric_values[player_name] = matrix[i, i]

            plot_bar(metric_values, metric_name.title(), os.path.join(output_dir, 'metric-{}.{}'.format(
                metric_name.lower().replace(' ', '-'), self.analyzer.img_format)), None, y_label=metric_name)

        labels = [self.analyzer.player_names[filename] for filename in file_names]

        # saves confusion matrix for cross-evaluation of each metric
        for metric_name, matrix in eval_matrix.items():
            file_path = os.path.join(output_dir, '{}-eval-matrix.{}'.format(
                metric_name.lower().replace(' ', '-'), self.analyzer.img_format))
            plot_confusion_matrix(
                matrix, file_path, labels + ['UNIFORM'], labels, CONF_MAT_COLOR_MAP,
                '{} Cross-Evaluation'.format(metric_name),
                'Agent Policy Using Player\'s Optimal Reward Function', 'Player\'s Observed Policy', 0, 1)
