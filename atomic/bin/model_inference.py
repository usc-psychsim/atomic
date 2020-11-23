import copy
import itertools
import os.path
import logging
from argparse import ArgumentParser

from plotly import express as px

from psychsim.probability import Distribution
from psychsim.pwl import WORLD, modelKey, stateKey

from atomic.definitions.map_utils import DEFAULT_MAPS
from atomic.parsing.parser import DataParser
from atomic.parsing.replayer import Replayer
from atomic.inference import DEFAULT_MODELS, DEFAULT_IGNORE
from atomic.model_learning.linear.post_process.clustering import load_cluster_reward_weights
-
class AnalysisParser(DataParser):
    def __init__(self, filename, maxDist=5, logger=logging):
        super().__init__(filename, maxDist, logger)
        self.name = os.path.splitext(os.path.basename(filename))[0]
        self.inference_data = []
        self.prediction_data = []
        self.models = set()
        self.expectation = None

    def draw_plot(self):
        if self.inference_data:
            fig = px.line(self.inference_data, x='Timestep', y='Belief', color='Model', range_y=[0, 1],
                          title='Inference {}'.format(self.name))
            fig.show()
        if self.prediction_data:
            fig = px.line(self.prediction_data, x='Timestep', y='Accuracy', range_y=[0, 1],
                          title='Prediction {}'.format(self.name))
            fig.show()

    def next_victim(self, world):
        """
        Generate an expectation about what room the player will enter next
        """
        player = world.agents[self.player_name()]
        agent = world.agents['ATOMIC']
        beliefs = agent.getBelief()
        if len(beliefs) == 1:
            agent_model, agent_beliefs = next(iter(beliefs.items()))
        else:
            raise NotImplementedError('Unable to generate predictions unless agent has unique model')
        location = world.getState(player.name, 'loc', unique=True)
        for player_model, player_model_prob in world.getModel(player.name, agent_beliefs).items():
            player_beliefs = player.models[player_model]['beliefs']
            fov = world.getState(player.name, 'vicInFOV', player_beliefs, unique=True)
#            if fov != 'none':
#                next_seen = Distribution({})
            logging.info('{}: FOV {}'.format(player_model, fov))
            logging.info('{}: Yellow {}'.format(player_model, world.getState(WORLD, 'ctr_{}_Gold'.format(location), player_beliefs)))
            logging.info('{}: Green {}'.format(player_model, world.getState(WORLD, 'ctr_{}_Green'.format(location), player_beliefs)))
        dist = Distribution({'Green': 1, 'Yellow': 0})
        return dist
 
    def pre_step(self, world):
        t = world.getState(WORLD, 'seconds', unique=True)
        entry = {'Timestep': t}
        for color, prob in self.next_victim(world).items():
            entry[color] = prob
        self.prediction_data.append(entry)

    def post_step(self, world, act):
        t = world.getState(WORLD, 'seconds', unique=True)
        player_name = self.player_name()
        player = world.agents[player_name]
        agent = world.agents['ATOMIC']
        # Store beliefs over player models
        beliefs = agent.getBelief()
        if len(beliefs) > 1:
            b_list = list(beliefs.values())
            for i in range(1, len(b_list)):
                for k in sorted(b_list[0].keys()):
                    if b_list[i][k] != b_list[0][k]:
                        logging.error('{}: {} != {} ({})'.format(k, str(b_list[i][k]), str(b_list[0][k]), i))
            else:
                logging.info('Identical. Sigh.')
            raise RuntimeError('Agent {} has {} possible models in true state'.format(agent.name, len(beliefs)))
        beliefs = next(iter(beliefs.values()))
        player_model = world.getFeature(modelKey(player_name), beliefs)
        for model in player_model.domain():
            entry = {'Timestep': t, 'Belief': player_model[model]}
            # Find root model (i.e., remove the auto-generated numbers from the name)
            while player.models[player.models[model]['parent']]['parent'] is not None:
                model = player.models[model]['parent']
            entry['Model'] = model[len(player_name) + 1:]
            self.inference_data.append(entry)

class Analyzer(Replayer):
    parser_class = AnalysisParser

    def __init__(self, files=[], maps=None, models=None, ignore_models=None, logger=logging):
        super().__init__(files, maps, models, ignore_models, logger)

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
        self.parser.draw_plot()


if __name__ == '__main__':
    # Process command-line arguments
    parser = ArgumentParser()
    parser.add_argument('fname', nargs='+',
                        help='Log file(s) (or directory of CSV files) to process')
    parser.add_argument('-1', '--1', action='store_true', help='Exit after the first run-through')
    parser.add_argument('-n', '--number', type=int, default=0,
                        help='Number of steps to replay (default is 0, meaning all)')
    parser.add_argument('-d', '--debug', default='WARNING', help='Level of logging detail')
    parser.add_argument('--ignore_reward', action='store_true', help='Do not consider alternate reward functions')
    parser.add_argument('--ignore_rationality', action='store_true', help='Do not consider alternate skill levels')
    parser.add_argument('--ignore_horizon', action='store_true', help='Do not consider alternate horizons')
    parser.add_argument('--reward_file', help='Name of CSV file containing alternate reward functions')
    args = vars(parser.parse_args())
    # Extract logging level from command-line argument
    level = getattr(logging, args['debug'].upper(), None)
    if not isinstance(level, int):
        raise ValueError('Invalid debug level: {}'.format(args['debug']))
    logging.basicConfig(level=level)
    # Look for reward file
    ignore = [dimension for dimension in DEFAULT_MODELS if args['ignore_{}'.format(dimension)]]
    if args['reward_file']:
        DEFAULT_MODELS['reward'] = {'cluster{}'.format(cluster): vector 
            for cluster, vector in load_cluster_reward_weights(args['reward_file']).items()}
    replayer = Analyzer(args['fname'], DEFAULT_MAPS, DEFAULT_MODELS, ignore, logging)
    if args['1']:
        replayer.process_files(args['number'], replayer.files[0])
    else:
        replayer.process_files(args['number'])
