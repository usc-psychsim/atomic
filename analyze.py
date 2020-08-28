from argparse import ArgumentParser
import collections
import itertools
import logging
import os.path
import sys
import traceback

from SandRMap import getSandRMap, getSandRVictims
from parser_no_pre import DataParser
from locations_no_pre import Locations
from maker import makeWorld
from atomic import set_player_models

maps = {'sparky': {'room_file': 'sparky_adjacency', 'victim_file': 'sparky_vic_locs'},
    'falcon': {'room_file': 'falcon_adjacency_v1.1_OCN', 'victim_file': 'falcon_vic_locs_v1.1_OCN'}}

# Possible player model parameterizations
models = collections.OrderedDict({'horizon': [2],
    'reward': [{'Green': 1,'Gold': 3}, {'Green': 1,'Gold': 1}],
    'training': [False], 
    'rationality': [0.5], 
    'selection': ['distribution']})

if __name__ == '__main__':
    # Process command-line arguments
    parser = ArgumentParser()
    parser.add_argument('fname',nargs='+',
        help='Log file(s) (or directory of CSV files) to process')
    parser.add_argument('-1','--1',action='store_true',help='Exit after the first run-through')
    parser.add_argument('-d','--debug',default='WARNING',help='Level of logging detail')
    args = vars(parser.parse_args())
    # Extract logging level from command-line argument
    level = getattr(logging, args['debug'].upper(), None)
    if not isinstance(level, int):
        raise ValueError('Invalid debug level: %s' % args['debug'])
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
        logger.debug('Full path: %s' % (fname))
        # Parse events from log file
        try:
            parser = DataParser(fname,logger=logger.getChild(DataParser.__name__))
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
                logger.debug('Map "%s" missing rooms %s' % (map_name,','.join(sorted(set(parser.locations)-map_table['rooms']))))
        else:
            logger.error('Unable to find matching map for rooms: %s' % (','.join(sorted(set(parser.locations)))))
            continue

        # Create PsychSim model
        logger.info('Creating world with "%s" map' % (map_name))
        try:
            world, triageAgent, observer, victims = makeWorld(parser.player_name(), map_table['start'], map_table['adjacency'], 
                map_table['victims'],False, True, logger.getChild('makeWorld'))
        except:
            logger.error(traceback.format_exc())
            logger.error('Unable to create world')
            if args['1']:
                break
            else:
                continue
        # Set player models for observer agent
        model_list = [{dimension: value[index] for index,dimension in enumerate(models)} 
            for value in itertools.product(*models.values())]
        for index,model in enumerate(model_list):
            model['name'] = '%s_belief_%d' % (triageAgent.name,index)
        set_player_models(world, observer.name, triageAgent.name, victims, model_list)
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
        try:
            parser.runTimeless(world, triageAgent.name, aes, 0, len(aes), len(aes),logger=logger.getChild('runTimeless'))
        except:
            logger.error(traceback.format_exc())
            logger.error('Unable to complete re-simulation')
            if args['1']:
                break
        Locations.clear()
