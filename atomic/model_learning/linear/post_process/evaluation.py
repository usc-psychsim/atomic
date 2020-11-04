import logging
import os
from atomic.definitions.world_map import WorldMap
from atomic.model_learning.linear.rewards import create_reward_vector
from atomic.model_learning.linear.analyzer import RewardModelAnalyzer
from model_learning.algorithms.max_entropy import THETA_STR
from model_learning.evaluation.linear import cross_evaluation
from model_learning.util.io import create_clear_dir, change_log_handler
from model_learning.util.plot import plot_bar, plot_confusion_matrix

__author__ = 'Pedro Sequeira'
__email__ = 'pedrodbs@gmail.com'

CONF_MAT_COLOR_MAP = 'inferno'
AGENT_RATIONALITY = 1 / 0.1  # inverse temperature


def evaluate_reward_models(analyzer, output_dir, clear=False, verbosity=1):
    """
    Evaluates the learned reward functions by using internal evaluation metrics. It mainly computes the mismatch
    between observed player policies and policies resulting from different reward functions, including the ones
    resulting from IRL for each player and the means for each reward cluster.
    :param RewardModelAnalyzer analyzer: the reward model analyzer containing the necessary data.
    :param str output_dir: the directory in which to save the results.
    :param bool clear: whether to clear the directory before processing.
    :param int verbosity: the verbosity level of the log file.
    :return:
    """
    create_clear_dir(output_dir, clear)
    change_log_handler(os.path.join(output_dir, 'post-process.log'), verbosity)

    file_names = list(analyzer.results)
    logging.info('\n=================================')
    logging.info('Performing cross-evaluation of reward functions for {} results...'.format(len(file_names)))

    # calculates eval metrics for each agent if using their own and others' rwd vectors
    trajectories = [analyzer.trajectories[filename] for filename in file_names]
    agent_names = [analyzer.agent_names[filename] for filename in file_names]
    agents = [trajectories[i][-1][0].agents[agent_names[i]] for i in range(len(trajectories))]
    map_locs = [list(analyzer.map_tables[filename]['rooms']) for filename in file_names]
    rwd_vectors = [create_reward_vector(agents[i], map_locs[i], WorldMap.get_move_actions(agents[i]))
                   for i in range(len(agents))]
    rwd_weights = [analyzer.results[filename].stats[THETA_STR] for filename in file_names]

    eval_matrix = cross_evaluation(
        trajectories, agent_names, rwd_vectors, rwd_weights, True,
        AGENT_RATIONALITY, analyzer.horizon, analyzer.prune, analyzer.processes)

    # gets internal evaluation (each agent against its own expert's reward function)
    for metric_name, matrix in eval_matrix.items():
        metric_values = {}
        for i, filename in enumerate(file_names):
            player_name = analyzer.get_player_name(filename)
            metric_values[player_name] = matrix[i, i]

        plot_bar(metric_values, metric_name.title(), os.path.join(output_dir, 'metric-{}.{}'.format(
            metric_name.lower().replace(' ', '-'), analyzer.img_format)), None, y_label=metric_name)

    labels = [analyzer.get_player_name(filename) for filename in file_names]

    # saves confusion matrix for cross-evaluation of each metric
    for metric_name, matrix in eval_matrix.items():
        file_path = os.path.join(output_dir, '{}-eval-matrix.{}'.format(
            metric_name.lower().replace(' ', '-'), analyzer.img_format))
        plot_confusion_matrix(
            matrix, file_path, labels + ['UNIFORM'], labels, CONF_MAT_COLOR_MAP,
            '{} Cross-Evaluation'.format(metric_name),
            'Agent Policy Using Player\'s Optimal Reward Function', 'Player\'s Observed Policy', 0, 1)
