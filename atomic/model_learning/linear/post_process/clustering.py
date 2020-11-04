import os
import logging
import numpy as np
from collections import OrderedDict
from model_learning.util.io import create_clear_dir, change_log_handler
from model_learning.util.plot import plot_bar
from model_learning.clustering.linear import cluster_linear_rewards, get_clusters_means, save_mean_cluster_weights, \
    save_clusters_info, plot_clustering_dendrogram, plot_clustering_distances
from atomic.definitions.world_map import WorldMap
from atomic.model_learning.linear.rewards import create_reward_vector
from atomic.model_learning.linear.analyzer import RewardModelAnalyzer

__author__ = 'Pedro Sequeira'
__email__ = 'pedrodbs@gmail.com'

DEF_DIST_THRESHOLD = .6
DEF_LINKAGE = 'ward'


def cluster_reward_weights(analyzer, output_dir,
                           linkage='ward', dist_threshold=DEF_DIST_THRESHOLD, clear=False, verbosity=1):
    """
    Analyzes the reward functions resulting from IRL optimization for each player log file.
    Performs clustering of reward functions based on the weight vectors and computes the mean rewards in each cluster.
    :param RewardModelAnalyzer analyzer: the reward model analyzer containing the necessary data.
    :param str output_dir: the directory in which to save the results.
    :param str linkage: the clustering linkage criterion.
    :param float dist_threshold: the distance above which clusters are not merged.
    :param bool clear: whether to clear the directory before processing.
    :param int verbosity: the verbosity level of the log file.
    :return:
    """
    create_clear_dir(output_dir, clear)
    change_log_handler(os.path.join(output_dir, 'post-process.log'), verbosity)

    file_names = list(analyzer.results)
    logging.info('\n=================================')
    logging.info('Analyzing models\' reward weights for {} results...'.format(len(file_names)))

    # performs cluster of reward weights
    results = [analyzer.results[filename] for filename in file_names]
    clustering, thetas = cluster_linear_rewards(results, linkage, dist_threshold)

    # gets rwd feature names with dummy info
    agent_name = analyzer.agent_names[file_names[0]]
    agent = analyzer.trajectories[file_names[0]][-1][0].agents[agent_name]
    locations = analyzer.map_tables[file_names[0]]['rooms']
    rwd_feat_names = create_reward_vector(agent, locations, WorldMap.get_move_actions(agent)).names

    # overall weight mean
    data = np.array([np.mean(thetas, axis=0), np.std(thetas, axis=0) / len(thetas)]).T.tolist()
    plot_bar(OrderedDict(zip(rwd_feat_names, data)),
             'Overall Mean Weights', os.path.join(output_dir, 'weights-mean.{}'.format(analyzer.img_format)),
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
                 os.path.join(output_dir, 'weights-mean-{}.{}'.format(cluster, analyzer.img_format)),
                 plot_mean=False)

    player_names = [analyzer.agent_names[filename] for filename in file_names]
    save_mean_cluster_weights(cluster_weights, os.path.join(output_dir, 'cluster-weights.csv'), rwd_feat_names)
    save_clusters_info(clustering, OrderedDict({'Player name': player_names, 'Filename': file_names}),
                       thetas, os.path.join(output_dir, 'clusters.csv'), rwd_feat_names)

    # dendrogram
    plot_clustering_dendrogram(
        clustering, os.path.join(output_dir, 'weights-dendrogram.{}'.format(analyzer.img_format)),
        player_names)

    plot_clustering_distances(
        clustering, os.path.join(output_dir, 'weights-distance.{}'.format(analyzer.img_format)))
