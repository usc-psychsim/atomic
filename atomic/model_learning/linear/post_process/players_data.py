import os
import logging
import numpy as np
from collections import OrderedDict
from model_learning.util.io import create_clear_dir, change_log_handler
from model_learning.util.plot import plot_bar
from atomic.definitions.plotting import plot_location_frequencies, plot_action_frequencies, plot_trajectories
from atomic.model_learning.linear.analyzer import RewardModelAnalyzer
from atomic.model_learning.stats import get_location_frequencies, get_action_frequencies

__author__ = 'Pedro Sequeira'
__email__ = 'pedrodbs@gmail.com'


def process_players_data(analyzer, output_dir, clear=False, verbosity=1):
    """
    Collects statistics regarding the players' behavior, mean location and action frequencies from the collected trajectories.
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
        map_table = analyzer.map_tables[filename]
        map_name = map_table['name'].lower()
        if map_name not in trajectories:
            map_tables[map_name] = map_table
            trajectories[map_name] = []
            traj_agents[map_name] = []
            location_data[map_name] = []
            action_data[map_name] = []

        trajectory = analyzer.trajectories[filename]
        trajectories[map_name].append(trajectory)

        agent = trajectory[-1][0].agents[analyzer.agent_names[filename]]
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
            loc_data, os.path.join(output_dir, '{}-loc-frequencies.{}'.format(map_name, analyzer.img_format)),
            'Mean Location Visitation Frequencies')

        act_data = action_data[map_name]
        act_data = {act: [np.mean([act_freqs[act] for act_freqs in act_data]),
                          np.std([act_freqs[act] for act_freqs in act_data]) / len(act_data)]
                    for act in all_actions}
        plot_action_frequencies(
            act_data,
            os.path.join(output_dir, '{}-action-frequencies.{}'.format(map_name, analyzer.img_format)),
            'Mean Action Execution Frequencies')

        # saves all player trajectories
        plot_trajectories(traj_agents[map_name], trajectories[map_name], locations, map_table['adjacency'],
                          os.path.join(output_dir, '{}-trajectories.{}'.format(map_name, analyzer.img_format)),
                          map_table['coordinates'], title='Player Trajectories')

        # saves trajectory length
        traj_len_data = OrderedDict(
            {analyzer.get_player_name(filename): len(analyzer.trajectories[filename])
             for filename in file_names})
        plot_bar(traj_len_data, 'Player Trajectory Length',
                 os.path.join(output_dir, '{}-trajectory-length.{}'.format(map_name, analyzer.img_format)))
