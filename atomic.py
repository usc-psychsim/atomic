from argparse import ArgumentParser
import logging
import os.path
import sys
import traceback

from SandRMap import getSandRMap, getSandRVictims
from parser_v2 import DataParser
from maker import makeWorld

maps = {'sparky': {'room_file': 'sparky_adjacency', 'victim_file': 'sparky_vic_locs'},
    'falcon': {'room_file': 'falcon_adjacency_v1.1_OCN', 'victim_file': 'falcon_vic_locs_v1.1_OCN'}}

if __name__ == '__main__':
    # Process command-line arguments
    parser = ArgumentParser()
    parser.add_argument('fname',nargs='+',help='Log file(s) (or directory of CSV files) to process')
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
        logger = logging.getLogger(os.path.basename(fname))
        logger.debug('Full path: %s' % (fname))
        # Parse events from log file
        try:
            parser = DataParser(fname,logger=logger.getChild(DataParser.__name__))
        except Exception as ex:
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
        world, triageAgent, agent, debug = makeWorld(parser.player_name(), map_table['start'], map_table['adjacency'], 
            map_table['victims'])
