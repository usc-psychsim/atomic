import argparse
import csv

from atomic.parsing.replayer import accumulate_files

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('fname', nargs='+',
                        help='Log file(s) (or directory of CSV files) to process')
    args = vars(parser.parse_args())
    adjacency = {}
    for fname in accumulate_files(args['fname']):
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
    for start, end_set in adjacency.items():
        print(start, sorted(end_set))
