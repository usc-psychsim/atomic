from argparse import ArgumentParser
import logging
import os.path
import sys
import traceback

from parser_v2 import DataParser

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

    # Get to work
    for fname in files:
        logger = logging.getLogger(os.path.basename(fname))
        logger.info('File: %s' % (fname))
        try:
            parser = DataParser(fname,logger=logger.getChild(DataParser.__name__))
        except Exception as ex:
            logger.error(traceback.format_exc())
            logger.error('Unable to parse log file')
            continue