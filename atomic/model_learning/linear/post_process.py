import logging
import os
import numpy as np
from collections import OrderedDict
from model_learning.algorithms.max_entropy import THETA_STR
from model_learning.clustering.linear import cluster_linear_rewards, get_clusters_means, save_mean_cluster_weights, \
    save_clusters_info, plot_clustering_distances, plot_clustering_dendrogram
from model_learning.metrics import evaluate_internal
from model_learning.planning import get_policy
from model_learning.util.plot import plot_bar
from atomic.definitions.world_map import WorldMap
from atomic.definitions.plotting import plot_location_frequencies, plot_action_frequencies, plot_trajectories
from atomic.model_learning.linear.rewards import create_reward_vector
from atomic.model_learning.stats import get_location_frequencies, get_action_frequencies
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
        save_mean_cluster_weights(cluster_weights, os.path.join(output_dir, 'cluster_weights.csv'), rwd_feat_names)
        save_clusters_info(clustering, OrderedDict({'Player name': player_names, 'Filename': file_names}),
                           thetas, os.path.join(output_dir, 'clusters.csv'), rwd_feat_names)

        # dendrogram
        plot_clustering_dendrogram(
            clustering, os.path.join(output_dir, 'weights-dendrogram.{}'.format(self.analyzer.img_format)),
            self.dist_threshold, player_names)

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

    def process_evaluation_metrics(self, output_dir):

        file_names = list(self.analyzer.results)
        logging.info('\n=================================')
        logging.info('Calculating evaluation metrics for {} results...'.format(len(file_names)))

        metrics_data = {}
        for filename in file_names:
            trajectory = self.analyzer.trajectories[filename]
            result = self.analyzer.results[filename]
            player_name = self.analyzer.player_names[filename]
            agent = trajectory[-1][0].agents[player_name]

            # player's observed "policy"
            player_states = [w.state for w, _ in trajectory]
            player_pi = [a for _, a in trajectory]

            # compute learner's policy
            rwd_vector = create_reward_vector(
                agent, list(self.analyzer.map_tables[filename]['rooms']), WorldMap.get_move_actions(agent))
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
                metrics_data[metric_name][player_name] = metric

        for metric_name, metric_values in metrics_data.items():
            plot_bar(metric_values, metric_name.title(), os.path.join(output_dir, 'metric-{}.{}'.format(
                metric_name.lower().replace(' ', '-'), self.analyzer.img_format)), None, y_label=metric_name)
