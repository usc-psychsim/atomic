from argparse import ArgumentParser
import itertools
import logging
import os.path
import sys
import traceback

import numpy
import plotly.express as px

from SandRMap import getSandRMap, getSandRVictims
from parser_no_pre import DataParser
from locations_no_pre import Locations
from maker import makeWorld
from atomic import set_player_models

from psychsim.pwl import WORLD, modelKey

maps = {'sparky': {'room_file': 'sparky_adjacency', 'victim_file': 'sparky_vic_locs'},
    'falcon': {'room_file': 'falcon_adjacency_v1.1_OCN', 'victim_file': 'falcon_vic_locs_v1.1_OCN'}}

# Possible player model parameterizations
models = {'horizon': {'myopic': 2, 'strategic': 4},
    'reward': {'preferyellow': {'Green': 1,'Gold': 3}, 'nopreference': {'Green': 1,'Gold': 1}},
    'rationality': {'unskilled': 0.5, 'skilled': 1}}

class AnalysisParser(DataParser):
    def __init__(self, filename, maxDist=5, logger=logging):
        super().__init__(filename, maxDist, logger)
        self.name = os.path.splitext(os.path.basename(filename))[0]
        self.inference_data = []
        self.prediction_data = []
        self.models = set()
        self.expectation = None

    def draw_plot(self):
        fig = px.line(self.inference_data,x='Timestep',y='Belief',color='Model',range_y=[0,1],
            title='Inference {}'.format(self.name))
        fig.show()
        fig = px.line(self.prediction_data,x='Timestep',y='Accuracy',range_y=[0,1],
            title='Prediction {}'.format(self.name))
        fig.show()

    def pre_step(self,world):
        player_name = self.player_name()
        agent = world.agents['ATOMIC']
        expectations = agent.expectation(player_name)
        if len(expectations) > 1:
            raise RuntimeError('Agent {} has {} possible models in true state'.format(agent.name,len(beliefs)))
        self.expectation = next(iter(expectations.values()))

    def post_step(self,world, act):
        t = world.getState(WORLD,'seconds',unique=True)
        player_name = self.player_name()
        player = world.agents[player_name]
        agent = world.agents['ATOMIC']
        # Store beliefs over player models
        beliefs = agent.getBelief()
        if len(beliefs) > 1:
            raise RuntimeError('Agent {} has {} possible models in true state'.format(agent.name,len(beliefs)))
        beliefs = next(iter(beliefs.values()))
        player_model = world.getFeature(modelKey(player_name),beliefs)
        for model in player_model.domain():
            entry = {'Timestep': t, 'Belief': player_model[model]}
            # Find root model (i.e., remove the auto-generated numbers from the name)
            while player.models[player.models[model]['parent']]['parent'] is not None:
                model = player.models[model]['parent']
            entry['Model'] = model
            self.inference_data.append(entry)
        # Store prediction probability
        if act is not None:
            if len(act) > 1:
                raise ValueError('Unable to evaluate accuracy of predicted action over actual action: {}'.format(act.domain()))
            act = act.first()
            value = 0
            for model,entry in self.expectation.items():
                value += entry['decision']['action'].get(act)*entry['probability']
            self.prediction_data.append({'Timestep': t, 'Accuracy': value})


if __name__ == '__main__':
    # Process command-line arguments
    parser = ArgumentParser()
    parser.add_argument('fname',nargs='+',
        help='Log file(s) (or directory of CSV files) to process')
    parser.add_argument('-1','--1',action='store_true',help='Exit after the first run-through')
    parser.add_argument('-n','--number',type=int,default=0,help='Number of steps to replay (default is 0, meaning all)')
    parser.add_argument('-d','--debug',default='WARNING',help='Level of logging detail')
    parser.add_argument('-s','--save',help='Filename to save PsychSim simulation under')
    parser.add_argument('--ignore_reward',action='store_true',help='Do not consider alternate reward functions')
    parser.add_argument('--ignore_rationality',action='store_true',help='Do not consider alternate skill levels')
    parser.add_argument('--ignore_horizon',action='store_true',help='Do not consider alternate horizons')
    args = vars(parser.parse_args())
    # Extract logging level from command-line argument
    level = getattr(logging, args['debug'].upper(), None)
    if not isinstance(level, int):
        raise ValueError('Invalid debug level: {}'.format(args['debug']))
    logging.basicConfig(level=level)
    # Extract files to process
    files = []
    for fname in args['fname']:
        if os.path.isdir(fname):
            # We have a directory full of log files to process
            files += [os.path.join(fname,name) for name in os.listdir(fname) 
                if os.path.splitext(name)[1] == '.csv' and os.path.join(fname,name) not in files]
        elif fname not in files:
            # We have a lonely single log file (that is not already in the list)
            files.append(fname)

    # Extract maps
    for map_name,map_table in maps.items():
        logger = logging.getLogger(map_name)
        map_table['adjacency'] = getSandRMap(fname=map_table['room_file'],logger=logger)
        map_table['rooms'] = set(map_table['adjacency'].keys())
        map_table['victims'] = getSandRVictims(fname=map_table['victim_file'])
        map_table['start'] = next(iter(map_table['adjacency'].keys()))
    # Get to work
    for fname in files:
        logger = logging.getLogger(os.path.splitext(os.path.basename(fname))[0])
        logger.debug('Full path: {}'.format(fname))
        # Parse events from log file
        try:
            parser = AnalysisParser(fname,logger=logger.getChild(DataParser.__name__))
        except:
            logger.error(traceback.format_exc())
            logger.error('Unable to parse log file')
            continue
        # Determine which map we're using
        for map_name,map_table in maps.items():
            if set(parser.locations) <= map_table['rooms']:
                # This map contains all of the rooms from this log
                break
            else:
                logger.debug('Map "{}" missing rooms {}'.format(map_name,','.join(sorted(set(parser.locations)-map_table['rooms']))))
        else:
            logger.error('Unable to find matching map for rooms: {}'.format(','.join(sorted(set(parser.locations)))))
            continue

        # Create PsychSim model
        logger.info('Creating world with "{}" map'.format(map_name))
        try:
            world, triageAgent, observer, victims = makeWorld(parser.player_name(), map_table['start'], map_table['adjacency'], 
                map_table['victims'],False, True, logger=logger.getChild('makeWorld'))
        except:
            logger.error(traceback.format_exc())
            logger.error('Unable to create world')
            if args['1']:
                break
            else:
                continue
        # Set player models for observer agent
        for dimension, entries in models.items():
            if args['ignore_{}'.format(dimension)]:
                first = True
                for key in list(entries.keys()):
                    if first:
                        first = False
                    else:
                        del entries[key]
        model_list = [{dimension: value[index] for index,dimension in enumerate(models)} 
            for value in itertools.product(*models.values())]
        for index,model in enumerate(model_list):
            model['name'] = '{}_{}'.format(triageAgent.name,'_'.join([model[dimension] for dimension in models]))
            for dimension in models:
                model[dimension] = models[dimension][model[dimension]]
        set_player_models(world, observer.name, triageAgent.name, victims, model_list)
        if args['save']:
            world.save(args['save'])
        # Replay actions from log file
        parser.victimsObj = victims
        try:
            aes, _ = parser.getActionsAndEvents(triageAgent.name)
        except:
            logger.error(traceback.format_exc())
            logger.error('Unable to extract actions/events')
            if args['1']:
                break
            else:
                continue
        if args['number'] == 0:
            last = len(aes)
        else:
            last = args['number']+1
        try:
            parser.runTimeless(world, triageAgent.name, aes, 0, last, len(aes), permissive=True)
        except:
            logger.error(traceback.format_exc())
            logger.error('Unable to complete re-simulation')
        parser.draw_plot()
        if args['1']:
            break
        Locations.clear()
