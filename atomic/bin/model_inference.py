import cProfile
import csv
from datetime import datetime
import itertools
import json
import os.path
import logging
import pytz
from argparse import ArgumentParser

import numpy as np
from plotly import express as px

from psychsim.probability import Distribution
from psychsim.pwl import WORLD, modelKey, stateKey

from atomic.parsing import ParsingProcessor
from atomic.definitions.map_utils import get_default_maps
from atomic.parsing.replayer import Replayer, filename_to_condition
from atomic.inference import DEFAULT_MODELS, DEFAULT_IGNORE


def plot_data(data, color_field, title):
    return px.line(data, x='Timestep', y='Belief', color=color_field, range_y=[0, 1], title=title)


class AnalysisParseProcessor(ParsingProcessor):
    condition_dist = None

    def __init__(self):
        super().__init__()
        self.model_data = []
        self.condition_data = []
        self.prediction_data = []
        self.models = set()
        self.expectation = None

    def draw_plot(self):
        name = os.path.splitext(os.path.basename(self.parser.file_name))[0]
        if self.model_data:
            fig = plot_data(self.model_data, 'Model', 'Model Inference {}'.format(name))
            fig.show()
        if self.condition_data:
            fig = plot_data(self.condition_data, 'Condition', 'Condition Inference {}'.format(name))
            fig.show()
        if self.prediction_data:
            fig = plot_data(self.prediction_data, 'Color', 'Prediction {}'.format(name))
            fig.show()

    def next_victim(self, world):
        """
        Generate an expectation about what room the player will enter next
        """
        player = world.agents[self.parser.player_name()]
        action = world.getAction(player.name, unique=True)
        if action['verb'] == 'triage_Green':
            # Triaging green as we speak
            return Distribution({'Green': 1})
        elif action['verb'] == 'triage_Gold':
            # Triaging yellow as we speak
            return Distribution({'Yellow': 1})
        # Not so obvious who will be next
        agent = world.agents['ATOMIC']
        beliefs = agent.getBelief()
        if len(beliefs) == 1:
            agent_model, agent_beliefs = next(iter(beliefs.items()))
        else:
            raise NotImplementedError('Unable to generate predictions unless agent has unique model')
        location = world.getState(player.name, 'loc', unique=True)
        prediction = None
        for player_model, player_model_prob in world.getModel(player.name, agent_beliefs).items():
            player_beliefs = player.models[player_model]['beliefs']
            fov = world.getState(player.name, 'vicInFOV', player_beliefs, unique=True)
            if fov in {'Yellow', 'Green'}:
                # The next victim found is the one the player is looking at now
                next_seen = Distribution({fov: 1})
            else:
                # The next victim found is one in the player's current location
                next_seen = {'Yellow': world.getState(WORLD, 'ctr_{}_Gold'.format(location), player_beliefs).expectation(),
                    'Green': world.getState(WORLD, 'ctr_{}_Green'.format(location), player_beliefs).expectation()}
                if sum(next_seen.values()) == 0:
                    # No victim in the current room
                    next_seen = {'Yellow': 1, 'Green': 1}
                next_seen = Distribution(next_seen)
                next_seen.normalize()
            if prediction is None:
                prediction = next_seen.scale_prob(player_model_prob)
            else:
                prediction = prediction.__class__({color: prob+next_seen[color]*player_model_prob
                    for color, prob in prediction.items()})
        return prediction
 
    def pre_step(self, world, log_entry=None):
        if log_entry is None:
            t = world.getState(WORLD, 'seconds', unique=True)
        else:
            t = log_entry[2]
#        if len(self.prediction_data) == 0 or self.prediction_data[-1]['Timestep'] != t:
#            # No prediction for this timestep yet
#            for color, prob in self.next_victim(world).items():
#                entry = {'Timestep': t, 'Belief': prob, 'Color': color}
#                self.prediction_data.append(entry)

    def post_step(self, world, act):
        t = world.getState(WORLD, 'seconds', unique=True)
        if len(self.model_data) == 0 or self.model_data[-1]['Timestep'] != t:
            # Haven't made some inference for this timestep (maybe wait until last one?)
            player_name = self.parser.player_name()
            player = world.agents[player_name]
            agent = world.agents['ATOMIC']
            # Store beliefs over player models
            beliefs = agent.getBelief()
            if len(beliefs) > 1:
                raise RuntimeError('Agent {} has {} possible models in true state'.format(agent.name, len(beliefs)))
            beliefs = next(iter(beliefs.values()))
            player_model = world.getFeature(modelKey(player_name), beliefs)
            for model in player_model.domain():
                entry = {'Timestep': t, 'Belief': player_model[model]}
                # Find root model (i.e., remove the auto-generated numbers from the name)
                while player.models[player.models[model]['parent']]['parent'] is not None:
                    model = player.models[model]['parent']
                entry['Model'] = model[len(player_name) + 1:]
                self.model_data.append(entry)
            if self.condition_dist:
                condition_dist = Distribution()
                for model, model_prob in player_model.items():
                    for condition, condition_prob in self.condition_dist[model_to_cluster(model)].items():
                        condition_dist.addProb(condition, model_prob*condition_prob)
                condition_dist.normalize()
                for condition, condition_prob in condition_dist.items():
                    self.condition_data.append({'Timestep': t, 'Belief': condition_prob, 'Condition': condition})


class Analyzer(Replayer):

    def __init__(self, files=[], maps=None, models=None, ignore_models=None, mission_times={}, logger=logging):
        super().__init__(files, maps, models, ignore_models, True, AnalysisParseProcessor(), logger)

        self.mission_times = mission_times
        # Set player models for observer agent
        if models is None:
            models = DEFAULT_MODELS
        if ignore_models is None:
            ignore_models = DEFAULT_IGNORE
        for dimension, entries in models.items():
            if dimension in ignore_models:
                first = True
                for key in list(entries.keys()):
                    if first:
                        first = False
                    else:
                        del entries[key]
        self.model_list = [{dimension: value[index] for index, dimension in enumerate(models)}
                           for value in itertools.product(*models.values()) if len(value) > 0]
        self.models = models

    def post_replay(self):
        for data_type, data in {'models': self.parser.model_data, 'conditions': self.parser.condition_data,
            'predictions': self.parser.prediction_data}.items():
            for entry in data:
                now = entry['Timestep'].to_pydatetime()
                epsilon = 1
                while epsilon > 0:
                    for t in self.mission_times:
                        if abs(now - t).total_seconds() < epsilon:
                            break
                    else:
                        # Didn't find a mathing time, so let's be more forgiving
                        epsilon += 1
                        continue
                    epsilon = 0
                minutes, seconds = self.mission_times[t]
                assert minutes < 10
                if data is self.parser.prediction_data and minutes < 5:
                    entry['Belief'] = 1 if entry['Color'] == 'Green' else 0
                entry['Timestep'] = (9-minutes)*60 + (60-seconds)
            if data:
                with open(self.parser.filename.replace('.csv','_Analysis-{}.tsv'.format(data_type)), 'w') as csvfile:
                    writer = csv.DictWriter(csvfile, data[0].keys(), delimiter='\t')
                    writer.writeheader()
                    for entry in data:
                        writer.writerow(entry)
        self.parser.draw_plot()

def load_clusters(fname):
    ignore = {'Cluster', 'Player name', 'Filename'}

    cluster_map = {}
    raw_weights = {}
    reward_weights = {}
    condition_map = {None: {}}
    with open(fname, 'r') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            cluster = int(row['Cluster'])
            weights = [np.array([float(value) for field, value in row.items() if field not in ignore])]
            raw_weights[cluster] = raw_weights.get(cluster, []) + weights
            cluster_map[row['Player name']] = cluster
            cluster_map[row['Filename']] = cluster
            condition = filename_to_condition(os.path.splitext(os.path.basename(row['Filename']))[0])
            condition_label = '{} {}'.format(condition['CondBtwn'], condition['CondWin'][1])
            if cluster not in condition_map:
                condition_map[cluster] = {}
            condition_map[cluster][condition_label] = condition_map[cluster].get(condition_label, 0) + 1
            # Update stats for universal cluster
#            raw_weights[None] = raw_weights.get(None, []) + weights
            condition_map[None][condition_label] = condition_map[cluster].get(condition_label, 0) + 1
    for cluster, weights in raw_weights.items():
        reward_weights[cluster] = np.mean(weights, axis=0)
        condition_map[cluster] = Distribution(condition_map[cluster])
        condition_map[cluster].normalize()
    condition_map[None] = Distribution(condition_map[None])
    condition_map[None].normalize()
    logging.info('Baseline conditions: {}'.format(', '.join(['P({})={}'.format(c, p) for c, p in sorted(condition_map[None].items())])))
    return reward_weights, cluster_map, condition_map

def apply_cluster_rewards(reward_weights, models=None):
    if models is None:
        models = DEFAULT_MODELS
    models['reward'] = {'cluster{}'.format(cluster): vector
        for cluster, vector in reward_weights.items()}

def model_to_cluster(model):
    try:
        return int(model.split('_')[-2][7:])
    except ValueError:
        return None

if __name__ == '__main__':
    # Process command-line arguments
    parser = ArgumentParser()
    parser.add_argument('fname', nargs='+',
                        help='Log file(s) (or directory of CSV files) to process')
    parser.add_argument('-1', '--1', action='store_true', help='Exit after the first run-through')
    parser.add_argument('-n', '--number', type=int, default=0,
                        help='Number of steps to replay (default is 0, meaning all)')
    parser.add_argument('-d', '--debug', default='WARNING', help='Level of logging detail')
    parser.add_argument('--profile', action='store_true', help='Run profiler')
    parser.add_argument('--ignore_reward', action='store_true', help='Do not consider alternate reward functions')
    parser.add_argument('--ignore_rationality', action='store_true', help='Do not consider alternate skill levels')
    parser.add_argument('--ignore_horizon', action='store_true', help='Do not consider alternate horizons')
    parser.add_argument('--reward_file', help='Name of CSV file containing alternate reward functions')
    parser.add_argument('-c','--clusters', help='Name of CSV file containing reward clusters to use as basis for player models')
    parser.add_argument('--metadata', help='Name of JSON file containing raw game log for this trial')
    args = vars(parser.parse_args())
    # Extract logging level from command-line argument
    level = getattr(logging, args['debug'].upper(), None)
    if not isinstance(level, int):
        raise ValueError('Invalid debug level: {}'.format(args['debug']))
    logging.basicConfig(level=level)
    # Look for reward file
    ignore = [dimension for dimension in DEFAULT_MODELS if args['ignore_{}'.format(dimension)]]
    mission_times = {}
    if args['metadata']:
        with open(args['metadata'], 'r') as log_file:
            for line in log_file:
                entry = json.loads(line)
                if 'mission_timer' in entry['data'] and entry['data']['mission_timer'] != 'Mission Timer not initialized.':
                    minutes, seconds = [int(value) for value in entry['data']['mission_timer'].split(':')]
                    timestamp = pytz.utc.localize(datetime.fromisoformat(entry['@timestamp'][:-1]))
                    mission_times[timestamp] = (minutes, seconds)
    if args['clusters']:
        import atomic.model_learning.linear.post_process.clustering as clustering

        reward_weights, cluster_map, condition_map = load_clusters(args['clusters'])
        AnalysisParseProcessor.condition_dist = condition_map
        apply_cluster_rewards(reward_weights)
    elif args['reward_file']:
        import atomic.model_learning.linear.post_process.clustering as clustering

        apply_cluster_rewards(clustering.load_cluster_reward_weights(args['reward_file']))
    replayer = Analyzer(args['fname'], get_default_maps(logging), DEFAULT_MODELS, ignore, mission_times, logging)
    if args['profile']:
        cProfile.run('replayer.process_files(args["number"])', sort=1)
    elif args['1']:
        replayer.process_files(args['number'], replayer.files[0])
    else:
        replayer.process_files(args['number'])
