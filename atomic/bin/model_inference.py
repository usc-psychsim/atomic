import configparser
import copy
import cProfile
import csv
from datetime import datetime
import itertools
import json
import logging
import os.path
import pytz
import traceback
from argparse import ArgumentParser

import numpy as np
from plotly import express as px

from psychsim.probability import Distribution
from psychsim.pwl import WORLD, modelKey, stateKey

from atomic.parsing import ParsingProcessor
from atomic.definitions.map_utils import get_default_maps
from atomic.parsing.replayer import Replayer, replay_parser, parse_replay_args, filename_to_condition
from atomic.inference import make_observer, create_player_models, DEFAULT_MODELS, DEFAULT_IGNORE


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

    def __init__(self, files=[], maps=None, models=None, ignore_models=[], mission_times={}, 
            rddl_file=None, action_file=None, feature_output=None, aux_file=None, logger=logging):
        super().__init__(files, maps, None, rddl_file, action_file, feature_output, aux_file, logger)

        self.models = None
        self.model_list = []
        self.player_models = None
        self.observer = None
        self.model_data = []
        self.condition_data = []
        self.prediction_data = []
        self.mission_times = mission_times
        self.decisions = {}
        self.stats = {}
        self.beliefs = None
        self.data = []
        self.data_fields = []

    def pre_replay(self, config=None, logger=logging):
        result = super().pre_replay(logger)
        if result is not True:
            # Failed
            return result
        try:
            if config: 
                self.player_models = self.configure_models(config)
                self.stats = {name: {} for name in self.player_models}
                self.beliefs = {name: Distribution({model['name']: 1/len(models) for model in models}) for name, models in self.player_models.items()}
        except:
            logger.error('Unable to create player models')
            logger.error(traceback.format_exc())
            return False
        return True

    def pre_step(self, logger=logging):
        super().pre_step(logger)
        self.previous = copy.deepcopy(self.world.state)
        for name, models in self.player_models.items():
            self.decisions[name] = {}
            for model in models:
                logger.debug(f'Generating decision for {name} under {model["name"]}')
                decision = self.world.agents[name].decide(model=model['name'], debug={'preserve_states': True})
                self.decisions[name][model['name']] = decision
                V = decision['V']
                for action, entry in V.items():
                    logger.info(f'{model["name"]}: V({action}) = {entry["__EV__"]}')
                    logger.info(', '.join([str(self.world.agents[name].reward(s, model=model['name'])) for s in entry['__S__']]))

    def post_step(self, actions, debug, logger=logging):
        super().post_step(actions, debug, logger)
        for name, models in self.player_models.items():
            prob = {}
            for model in models:
                record = {'Msg': self.t, 'Player': name}
                agent = self.world.agents[name]
                record.update(agent.models[model['name']]['parameters'])
                prob[model['name']] = self.decisions[name][model['name']]['action'][actions[name]]
                record['Prob'] = prob[model['name']]
                self.beliefs[name][model['name']] *= prob[model['name']]
                self.data.append(record)
                if len(self.data_fields) == 0:
                    self.data_fields = list(record.keys())
            self.beliefs[name].normalize()
            logger.info(self.beliefs[name])

    def post_replay(self, logger=logging):
        super().post_replay(logger)
        with open(self.parser.filename.replace('.metadata','_models.tsv'), 'w') as csvfile:
            writer = csv.DictWriter(csvfile, self.data_fields, delimiter='\t')
            writer.writeheader()
            for record in self.data:
                writer.writerow(record)
            for name, dist in self.beliefs.items():
                for model, prob in dist.items():
                    record = {'Msg': 'END', 'Player': name}
                    record.update(self.world.agents[name].models[model]['parameters'])
                    record['Prob'] = prob
                    writer.writerow(record)
#        self.draw_plot()

    def configure_models(self, fname):
        config = configparser.ConfigParser()
        config.read(fname)
        models = {key: json.loads(values) for key, values in config.items('models')}
        if 2 in models.get('reward', []):
            # Add visitation reward
            victims = self.victim_counts
        else:
            victims = None
        self.model_list = [{dimension: value[index] for index, dimension in enumerate(models)}
                           for value in itertools.product(*models.values()) if len(value) > 0]
        self.models = models
        return create_player_models(self.world, {player_name: self.model_list[:] for player_name in self.parser.agentToPlayer}, victims)

    def draw_plot(self):
        name = os.path.splitext(os.path.basename(self.parser.filename))[0]
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
    parser = replay_parser()
    parser.add_argument('--reward_file', help='Name of CSV file containing alternate reward functions')
    parser.add_argument('-c','--clusters', help='Name of CSV file containing reward clusters to use as basis for player models')
    args = parse_replay_args(parser)
    if args['clusters']:
        import atomic.model_learning.linear.post_process.clustering as clustering

        reward_weights, cluster_map, condition_map = load_clusters(args['clusters'])
        AnalysisParseProcessor.condition_dist = condition_map
        apply_cluster_rewards(reward_weights)
    elif args['reward_file']:
        import atomic.model_learning.linear.post_process.clustering as clustering

        apply_cluster_rewards(clustering.load_cluster_reward_weights(args['reward_file']))
    replayer = Analyzer(args['fname'], rddl_file=args['rddl'], action_file=args['actions'], feature_output=args['feature_file'], aux_file=args['aux'], logger=logging)
    replayer.parameterized_replay(args)
