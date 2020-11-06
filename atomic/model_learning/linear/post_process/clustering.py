import os
import logging
import numpy as np
import pandas as pd
from collections import OrderedDict
from model_learning.clustering.evaluation import evaluate_clustering
from model_learning.util.io import create_clear_dir, change_log_handler
from model_learning.util.plot import plot_bar
from model_learning.clustering.linear import cluster_linear_rewards, get_clusters_means, save_mean_cluster_weights, \
    save_clusters_info, plot_clustering_dendrogram, plot_clustering_distances
from atomic.parsing.replayer import SUBJECT_ID_TAG, COND_MAP_TAG, TRIAL_TAG, COND_TRAIN_TAG
from atomic.definitions.world_map import WorldMap
from atomic.model_learning.linear.rewards import create_reward_vector
from atomic.model_learning.linear.analyzer import RewardModelAnalyzer

__author__ = 'Pedro Sequeira'
__email__ = 'pedrodbs@gmail.com'

DEF_DIST_THRESHOLD = .6
DEF_STDS = 3
DEF_LINKAGE = 'ward'


def load_cluster_reward_weights(file_path):
    """
    Loads the linear reward weights for a set of clusters from a CSV file.
    :param str file_path: the path to the file from which to load the reward weights.
    :rtype: dict[str, np.ndarray]
    :return: a dictionary containing entries in the form `cluster_id` -> `reward_weights`.
    """
    assert os.path.isfile(file_path), 'Could not found CSV file at {}'.format(file_path)
    data = pd.read_csv(file_path, index_col=0)
    return {idx: np.array(row) for idx, row in data.iterrows()}


def load_datapoints_clusters(file_path):
    """
    Loads the clustering results for a set of datapoints from a CSV file.
    :param str file_path: the path to the file from which to load the clusters.
    :rtype: dict[str, int]
    :return: a dictionary containing the cluster id assigned to each datapoint, i.e., entries in the form
    `datapoint filename` -> `cluster idx`.
    """
    assert os.path.isfile(file_path), 'Could not found CSV file at {}'.format(file_path)
    data = pd.read_csv(file_path, index_col=2)  # index='Filename'
    return {idx: row['Cluster'] for idx, row in data.iterrows()}


def cluster_reward_weights(analyzer, output_dir,
                           linkage='ward', dist_threshold=DEF_DIST_THRESHOLD, stds=DEF_STDS,
                           clear=False, verbosity=1):
    """
    Analyzes the reward functions resulting from IRL optimization for each player log file.
    Performs clustering of reward functions based on the weight vectors and computes the mean rewards in each cluster.
    :param RewardModelAnalyzer analyzer: the reward model analyzer containing the necessary data.
    :param str output_dir: the directory in which to save the results.
    :param str linkage: the clustering linkage criterion.
    :param float dist_threshold: the distance above which clusters are not merged.
    :param float stds: the number of standard deviations above the gradient mean used for automatic cluster detection.
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
    clustering, thetas = cluster_linear_rewards(results, linkage, dist_threshold, stds)

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
    logging.info('Found {} clusters at max. distance: {:.2f}'.format(
        clustering.n_clusters_, clustering.distance_threshold))
    for cluster in sorted(cluster_weights):
        idxs = clusters[cluster]
        data = cluster_weights[cluster]
        data[1] = data[1] / len(idxs)
        with np.printoptions(precision=2, suppress=True):
            logging.info('\tCluster {}: {}, \n\tmean: {}\n'.format(cluster, idxs, data[0]))
        plot_bar(OrderedDict(zip(rwd_feat_names, data.T.tolist())),
                 'Mean Weights for Cluster {}'.format(cluster),
                 os.path.join(output_dir, 'weights-mean-{}.{}'.format(cluster, analyzer.img_format)),
                 plot_mean=False)

    player_names = [analyzer.get_player_name(file_name) for file_name in file_names]
    save_mean_cluster_weights(cluster_weights, os.path.join(output_dir, 'cluster-weights.csv'), rwd_feat_names)
    save_clusters_info(clustering, OrderedDict({'Player name': player_names, 'Filename': file_names}),
                       thetas, os.path.join(output_dir, 'clusters.csv'), rwd_feat_names)

    # dendrogram
    plot_clustering_dendrogram(
        clustering, os.path.join(output_dir, 'weights-dendrogram.{}'.format(analyzer.img_format)),
        player_names)
    plot_clustering_distances(
        clustering, os.path.join(output_dir, 'weights-distance.{}'.format(analyzer.img_format)))

    # gets different data partitions according to maps, conditions, subjects, etc
    gt_labels = {
        'Subject': [analyzer.trial_conditions[file_name][SUBJECT_ID_TAG] for file_name in file_names],
        'Map Condition': [analyzer.trial_conditions[file_name][COND_MAP_TAG][0] for file_name in file_names],
        'Dynamic Map Cond.': [analyzer.trial_conditions[file_name][COND_MAP_TAG][1] for file_name in file_names],
        'Train Condition': [analyzer.trial_conditions[file_name][COND_TRAIN_TAG] for file_name in file_names]
    }
    subject_min_trials = {}
    for i, file_name in enumerate(file_names):
        subj_label = gt_labels['Subject'][i]
        subj_trial = int(analyzer.trial_conditions[file_name][TRIAL_TAG])
        if subj_label not in subject_min_trials or subj_trial < subject_min_trials[subj_label]:
            subject_min_trials[subj_label] = subj_trial
    gt_labels['Trial'] = [
        int(analyzer.trial_conditions[file_name][TRIAL_TAG]) -
        subject_min_trials[gt_labels['Subject'][i]] for i, file_name in enumerate(file_names)]

    # performs clustering evaluation according to the different gt partitions and combinations thereof
    evaluate_clustering(clustering, gt_labels, output_dir, analyzer.img_format, 3)
