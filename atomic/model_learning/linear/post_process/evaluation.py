import logging
import os
import numpy as np
from collections import OrderedDict
from atomic.definitions.world_map import WorldMap
from atomic.model_learning.linear.post_process.clustering import load_cluster_reward_weights, load_datapoints_clusters
from atomic.model_learning.linear.rewards import create_reward_vector
from atomic.model_learning.linear.analyzer import RewardModelAnalyzer
from model_learning.algorithms.max_entropy import THETA_STR
from model_learning.clustering.linear import save_mean_cluster_weights
from model_learning.evaluation.linear import cross_evaluation
from model_learning.util.io import create_clear_dir, change_log_handler
from model_learning.util.plot import plot_bar, plot_confusion_matrix

__author__ = 'Pedro Sequeira'
__email__ = 'pedrodbs@gmail.com'

CONF_MAT_COLOR_MAP = 'inferno'
AGENT_RATIONALITY = 1 / 0.1  # inverse temperature

# predefined reward models
# Before Mid, After Mid, Loc Freq, Triaged Green, Triaged Gold, See White, See Red, Move N, Move E, Move S, Move W
REWARD_MODELS = OrderedDict({
    'Uniform': np.full(11, 1. / 11),
    'Prefer Gold': np.array([0, 0, 0, 0.2, 0.8, 0, 0, 0, 0, 0, 0]),
    'Prefer Green': np.array([0, 0, 0, 0.8, 0.2, 0, 0, 0, 0, 0, 0]),
    'Save Victims': np.array([0, 0, 0, 0.5, 0.5, 0, 0, 0, 0, 0, 0]),
    'Explorer': np.array([0, 0, -1, 0, 0, 0, 0, 0, 0, 0, 0]),
    'Avoid Saved': np.array([0, 0, 0, 0, 0, -1, 0, 0, 0, 0, 0]),
    'Too Late': np.array([0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0]),
    'Move N-S': np.array([0, 0, 0, 0, 0, 0, 0, 0.5, 0, 0.5, 0]),
    'Move E-W': np.array([0, 0, 0, 0, 0, 0, 0, 0, 0.5, 0, 0.5]),
})


def evaluate_reward_models(analyzer, output_dir, cluster_rwds_file=None, datapoint_clusters_file=None,
                           clear=False, verbosity=1):
    """
    Evaluates the learned reward functions by using internal evaluation metrics. It mainly computes the mismatch
    between observed player policies and policies resulting from different reward functions, including the ones
    resulting from IRL for each player and the means for each reward cluster.
    :param RewardModelAnalyzer analyzer: the reward model analyzer containing the necessary data.
    :param str output_dir: the directory in which to save the results.
    :param str cluster_rwds_file: the path to the file from which to load the clusters' reward weights.
    :param str datapoint_clusters_file: the path to the file from which to load the datapoints' clusters.
    :param bool clear: whether to clear the directory before processing.
    :param int verbosity: the verbosity level of the log file.
    :return:
    """
    create_clear_dir(output_dir, clear)
    change_log_handler(os.path.join(output_dir, 'post-process.log'), verbosity)
    file_names = list(analyzer.results)

    # tries to load cluster info and sorts datapoints by cluster
    if datapoint_clusters_file is not None and os.path.isfile(datapoint_clusters_file):
        clusters = load_datapoints_clusters(datapoint_clusters_file)
        file_names.sort(key=lambda f: clusters[f] if f in clusters else -1)

    logging.info('\n=================================')
    logging.info('Performing cross-evaluation of reward functions for {} results...'.format(len(file_names)))

    # first gets data needed to compute players' "observed" policies
    # trajectories = [analyzer.trajectories[filename] for filename in file_names]
    trajectories = [analyzer.trajectories[filename] for filename in file_names]
    agent_names = [analyzer.agent_names[filename] for filename in file_names]
    agents = [trajectories[i][-1][0].agents[agent_names[i]] for i in range(len(trajectories))]
    map_locs = [list(analyzer.map_tables[filename]['rooms']) for filename in file_names]
    rwd_vectors = [create_reward_vector(agents[i], map_locs[i], WorldMap.get_move_actions(agents[i]))
                   for i in range(len(agents))]

    # saves nominal weight vectors/profiles
    save_mean_cluster_weights({k: v.reshape(1, -1) for k, v in REWARD_MODELS.items()},
                              os.path.join(output_dir, 'nominal-weights.csv'), rwd_vectors[0].names)

    # calculates eval metrics for each player policy against nominal and cluster-based policies
    num_states = analyzer.num_trajectories * analyzer.length
    rwd_weights = OrderedDict(REWARD_MODELS)
    if cluster_rwds_file is not None and os.path.isfile(cluster_rwds_file):
        rwd_weights.update(
            {'Cluster {}'.format(k): v for k, v in load_cluster_reward_weights(cluster_rwds_file).items()})
    eval_matrix = cross_evaluation(
        trajectories, agent_names, rwd_vectors, list(rwd_weights.values()),
        AGENT_RATIONALITY, analyzer.horizon, analyzer.prune, analyzer.processes, num_states, analyzer.seed)

    # saves confusion matrix for cross-evaluation of each metric
    x_labels = [analyzer.get_player_name(filename) for filename in file_names]
    y_labels = list(rwd_weights.keys())
    for metric_name, matrix in eval_matrix.items():
        file_path = os.path.join(output_dir, '{}-cross-eval-matrix.{}'.format(
            metric_name.lower().replace(' ', '-'), analyzer.img_format))
        plot_confusion_matrix(
            matrix, file_path, x_labels, y_labels, CONF_MAT_COLOR_MAP,
            '{} Cross-Evaluation'.format(metric_name),
            'Agent Policy Using Player\'s Optimal Reward Function', 'Player\'s Observed Policy', 0, 1)

    # calculates eval metrics for each player policy against its optimal reward weights discovered via IRL (self-eval)
    metrics_values = {}
    for i, filename in enumerate(file_names):
        eval_matrix = cross_evaluation(
            [trajectories[i]], [agent_names[i]], [rwd_vectors[i]], [analyzer.results[filename].stats[THETA_STR]],
            AGENT_RATIONALITY, analyzer.horizon, analyzer.prune, analyzer.processes, num_states, analyzer.seed + i)

        # organizes by metric name and then by player
        player_name = analyzer.get_player_name(filename)
        for metric_name, matrix in eval_matrix.items():
            if metric_name not in metrics_values:
                metrics_values[metric_name] = {}
            metrics_values[metric_name][player_name] = matrix[0, 0]

    # plots mean self-eval performance
    for metric_name, metric_values in metrics_values.items():
        plot_bar(metric_values, metric_name.title(), os.path.join(output_dir, '{}-self-eval.{}'.format(
            metric_name.lower().replace(' ', '-'), analyzer.img_format)), None, y_label=metric_name)
