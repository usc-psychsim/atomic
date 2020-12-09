import copy
import os
import logging
import numpy as np
from collections import OrderedDict
from model_learning.util.io import create_clear_dir, change_log_handler
from model_learning.util.plot import plot_bar
from atomic.definitions.features import get_mission_seconds_key
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
    map_files = {}
    for file_name in file_names:
        map_table = analyzer.map_tables[file_name]
        map_name = map_table.name.lower()
        if map_name not in map_files:
            map_files[map_name] = []
        map_files[map_name].append(file_name)

    for map_name, files in map_files.items():
        map_table = analyzer.map_tables[files[0]]
        locations = map_table.rooms_list
        trajectories = [analyzer.trajectories[filename] for filename in files]
        agents = [trajectories[i][-1][0].agents[analyzer.agent_names[files[i]]] for i in range(len(files))]

        # saves mean location frequencies
        location_data = [get_location_frequencies(agents[i], [trajectories[i]], map_table.rooms_list)
                         for i in range(len(files))]
        location_data = {loc: [np.mean([loc_freqs[loc] for loc_freqs in location_data]),
                               np.std([loc_freqs[loc] for loc_freqs in location_data]) / len(location_data)]
                         for loc in locations}
        plot_location_frequencies(
            location_data, os.path.join(output_dir, '{}-loc-frequencies.{}'.format(map_name, analyzer.img_format)),
            'Mean Location Visitation Frequencies')

        # saves mean action frequencies
        act_data = [get_action_frequencies(agents[i], [trajectories[i]]) for i in range(len(files))]
        act_data = [{str(a).replace('{}-'.format(agents[i].name), '').replace('_', ' '): val
                     for a, val in act_data[i].items()}
                    for i in range(len(act_data))]
        all_actions = sorted(set([a for act_freqs in act_data for a in act_freqs]))
        act_data = OrderedDict({
            act: [np.mean([act_freqs[act] for act_freqs in act_data if act in act_freqs]),
                  np.std([act_freqs[act] for act_freqs in act_data if act in act_freqs]) / len(act_data)]
            for act in all_actions})
        plot_action_frequencies(
            act_data, os.path.join(output_dir, '{}-action-frequencies.{}'.format(map_name, analyzer.img_format)),
            'Mean Action Execution Frequencies')

        # saves all player trajectories
        plot_trajectories(agents, trajectories, locations, map_table.adjacency,
                          os.path.join(output_dir, '{}-trajectories.{}'.format(map_name, analyzer.img_format)),
                          map_table.coordinates, title='Player Trajectories')

    # saves trajectory length
    traj_len_data = OrderedDict(
        {analyzer.get_player_name(file_name): len(analyzer.trajectories[file_name]) for file_name in file_names})
    traj_len_data = {name: traj_len_data[name] for name in sorted(traj_len_data)}
    plot_bar(traj_len_data, 'Player Trajectory Length',
             os.path.join(output_dir, 'trajectory-length.{}'.format(analyzer.img_format)))

    # saves game mission times
    mission_time_data = {}
    for file_name in file_names:
        mission_time_feat = get_mission_seconds_key()
        world = analyzer.trajectories[file_name][-1][0]
        state = copy.deepcopy(world.state)
        state.select(True)
        mission_time_data[analyzer.get_player_name(file_name)] = world.getFeature(mission_time_feat, state, True)
    mission_time_data = {name: mission_time_data[name] for name in sorted(mission_time_data)}
    plot_bar(mission_time_data, 'Player Mission Time (secs)',
             os.path.join(output_dir, 'mission-time.{}'.format(analyzer.img_format)))
