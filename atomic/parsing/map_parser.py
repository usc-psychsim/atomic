import argparse
import csv

from psychsim.action import ActionSet
from atomic.parsing.replayer import accumulate_files, Replayer
from atomic.parsing.parser import ACTION

class ReplayLight(Replayer):
    def replay(self, events, duration, logger):
        for event in events:
            if event[0] == ACTION:
                for entry in event[1]:
                    if isinstance(entry, ActionSet):
                        print(entry)
                        
def extract_adjacency(fname, adjacency=None):
    if adjacency is None:
        adjacency = {}
    print(fname)
    with open(fname, 'r') as csvfile:
        reader = csv.DictReader(csvfile)
        last_room = None
        for row in reader:
            if row['Room_in'] != 'None':
                if last_room is None:
                    # First room
                    last_room = {key: value for key, value in row.items() if key in ['Room_in', 'x', 'z']}
                    if last_room['Room_in'] not in adjacency:
                        adjacency[last_room['Room_in']] = {}
                    assert last_room['Room_in'] == next(iter(adjacency.keys()))
                elif row['Room_in'] != last_room['Room_in']:
                    # Player has moved
                    if row['x'] > last_room['x']:
                        assert row['z'] == last_room['z'], 'Moving to {} from {} caused ambiguous change in XY coordinates'.format(row['Room_in'], last_room['Room_in'])
                        direction = 'E'
                    elif row['x'] < last_room['x']:
                        assert row['z'] == last_room['z'], 'Moving to {} from {} caused ambiguous change in XY coordinates'.format(row['Room_in'], last_room['Room_in'])
                        direction = 'W'
                    elif row['z'] > last_room['z']:
                        direction = 'N'
                    else:
                        assert row['z'] < last_room['z'], 'Moving to {} from {} caused no change in XY coordinates'.format(row['Room_in'], last_room['Room_in'])
                        direction = 'S'
                    assert direction not in adjacency[last_room['Room_in']], 'Moving {} from {} results in {}, but previously resulted in {}'.format(direction, last_room['Room_in'], row['Room_in'], adjacency[last_room['Room_in']][direction])
                    adjacency[last_room['Room_in']][direction] = row['Room_in']
                    if row['Room_in'] not in adjacency:
                        adjacency[row['Room_in']] = {}
                    last_room = {key: value for key, value in row.items() if key in ['Room_in', 'x', 'z']}
                else:
                    last_room['x'] = row['x']
                    last_room['z'] = row['z']

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('fname', nargs='+',
                        help='Log file(s) (or directory of CSV files) to process')
    parser.add_argument('-c', '--create', action='store_true', help='Create adjacency matrix from scratch')
    args = vars(parser.parse_args())

    if args['create']:
        adjacency = {}
        for fname in accumulate_files(args['fname']):
            extract_adjacency(fname, adjacency)
        for start, end_set in adjacency.items():
            print(start, sorted(end_set))
    else:
        replayer = ReplayLight(args['fname'])
        replayer.process_files()