import configparser
import copy
import cProfile
import csv
from datetime import datetime
import itertools
import json
import logging
import os.path
import re
import traceback
from argparse import ArgumentParser

import numpy as np
import pandas
from plotly import express as px

from psychsim.probability import Distribution
from psychsim.pwl import WORLD, modelKey, stateKey

from atomic.definitions.map_utils import get_default_maps
from atomic.parsing.replay_features import *
from atomic.inference import *


def plot_data(data, color_field, title):
    return px.line(data, x='Timestep', y='Belief', color=color_field, range_y=[0, 1], title=title)


class Analyzer(FeatureReplayer):

    def __init__(self, files=[], trials=None, config=None, maps=None, rddl_file=None, action_file=None, aux_file=None, logger=logging, output=None):
        super().__init__(files=files, trials=trials, config=config, maps=maps, rddl_file=rddl_file, action_file=action_file, aux_file=aux_file, output=output,
            logger=logger)

        if config:
            self.models = {key: json.loads(values) for key, values in self.config.items('models')}
            # Build up all combinations of values along the dimensions given
            self.model_list = [{dimension: value[index] for index, dimension in enumerate(self.models)}
                               for value in itertools.product(*self.models.values()) if len(value) > 0]
        self.beliefs = {}
        self.model_data = pandas.DataFrame()
        self.decisions = {}
        self.debug_data = {}
        self.model_columns = None

    def pre_replay(self, parser, logger=logging):
        result = super().pre_replay(parser, logger)
        if result is None:
            # Failed
            return result
        if self.models and 2 in self.models.get('reward', []):
            # Add visitation reward
            victims = self.victim_counts
        else:
            victims = None
        try:
            player_models = create_player_models(result.world, {player_name: self.model_list[:] for player_name in parser.agentToPlayer}, victims)
            self.beliefs[parser.jsonFile] = {name: Distribution({model['name']: 1/len(models) for model in models}) 
                for name, models in player_models.items()}
            self.decisions[parser.jsonFile] = {name: {} for name in player_models}
        except:
            logger.error('Unable to create player models')
            logger.error(traceback.format_exc())
            return None
        state = VectorDistributionSet()
        for name, belief in self.beliefs[parser.jsonFile].items():
            result.world.setFeature(modelKey(name), belief, state=state)
        tree = {}
        self.debug_data[parser.jsonFile] = []
        return result

    def pre_step(self, world, parser, logger=logging):
        super().pre_step(world, logger)
        #<SIMULATE>
#        debug_s = {ag_name: {'preserve_states': True} for ag_name in parser.agentToPlayer}
#        world.step(real=False, debug=debug_s) # This is where the script hangs
        #</SIMULATE>
        for name, models in self.beliefs[parser.jsonFile].items():
            self.decisions[parser.jsonFile][name].clear()
            for model in models.domain():
                logger.debug(f'Generating decision for {name} under {model}')
                self.decisions[parser.jsonFile][name][model] = world.agents[name].decide(model=model)

    def post_step(self, world, actions, t, parser, debug, logger=logging):
        super().post_step(world, actions, t, parser, debug, logger)
        for name, models in self.decisions[parser.jsonFile].items():
            prob = {}
            for model, decision in models.items():
                try:
                    prob[model] = decision['action'][actions[name]]
                except KeyError:
                    # Zero probability, probably because of illegal action
                    prob[model] = decision['action'].epsilon
                self.beliefs[parser.jsonFile][name][model] *= prob[model]
            self.beliefs[parser.jsonFile][name].normalize()
            logger.debug(self.beliefs[parser.jsonFile][name])
            for model in models:
                record = filename_to_condition(parser.jsonFile)
                record['Message'] = t
                participant = parser.agentToPlayer[name]
                if re.match(REGEX_INDIVIDUAL, participant):
                    record['Participant'] = participant
                else:
                    record['Participant'] = parser.jsonParser.subjects[participant]
                agent = world.agents[name]
                record.update(agent.models[model]['parameters'])
                record['Probability'] = prob[model]
                record['Belief'] = self.beliefs[parser.jsonFile][name][model]
                if self.model_columns is None:
                    self.model_columns = list(record.keys())
                self.model_data = self.model_data.append(record, ignore_index=True)

            self.debug_data[parser.jsonFile].append({"WORLD": world,
                "AGENT_DEBUG": self.decisions[parser.jsonFile],
                "AGENT_ACTIONS": actions})

    def finish(self):
        super().finish()
        if self.feature_output and len(self.model_data) > 0:
            root, ext = os.path.splitext(self.feature_output)
            self.model_data.to_csv(f'{root}_models{ext}', index=False, columns=self.model_columns)

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

def model_cmd_parser():
    # Process command-line arguments
    parser = feature_cmd_parser()
    parser.add_argument('-c','--clusters', help='Name of CSV file containing reward clusters to use as basis for player models')
    return parser

if __name__ == '__main__':
    parser = model_cmd_parser()
    args = parse_replay_args(parser)
    if args['clusters']:
        import atomic.model_learning.linear.post_process.clustering as clustering

        reward_weights, cluster_map, condition_map = load_clusters(args['clusters'])
        AnalysisParseProcessor.condition_dist = condition_map
        apply_cluster_rewards(reward_weights)
    replayer = Analyzer(args['fname'], args['trials'], args['config'], rddl_file=args['rddl'], action_file=args['actions'], aux_file=args['aux'], logger=logging, output=args['output'])
    replayer.parameterized_replay(args)
