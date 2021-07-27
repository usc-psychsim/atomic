import argparse
import csv
import itertools as its
import json

from psychsim.action import ActionSet
from atomic.definitions.map_utils import getSandRMap

def verify_adjacency(fname, adjacency_matrix):
    errors = set()
    with open(fname, 'r') as csvfile:
        reader = csv.DictReader(csvfile)
        last_room = None
        for row in reader:
            if row['Room_in'] != 'None':
                if last_room is None:
                    # First room
                    last_room = row['Room_in']
                elif row['Room_in'] != last_room:
                    # Player has moved
                    if row['Room_in'] not in adjacency_matrix[last_room].values():
                        errors.add((last_room, row['Room_in']))
                    last_room = row['Room_in']
    return errors


def read_semantic_map(map_file):    
    #extract parent room and child areas from JSON file
    orig_map = json.load(open(map_file,'r'))
    
    return extract_map(orig_map)
    
def extract_map(orig_map):
    #extracting portal names and storing them to use in edge creation
    #indices from this list become the portal IDs in the graph
    portal_node_names = []
    for n in orig_map['connections']:
        if n['bounds']['type'] == 'rectangle':
            portal_node_names.append(n['id'])
    #ditto
    room_node_names = {}
    for m in orig_map['locations']:
        if 'child_locations' not in m:
            room_node_names[m['id']] = m['bounds']['coordinates']
    # creating edges
    # room edges contains edges going each direction
    # portal edges are split into two directions for DGL
    # bidirectional edges can also be done in DGL, but is explicit here for clarity
    # aget edges go to every physical node and vice-versa
    room_edges = []
    portal_room_edges = []
    room_portal_edges = []
    for i in orig_map['connections']:
        if 'extension' in i['type']:
            room_indices = []
            for k in i['connected_locations']:
                room_indices.append(k)
            room_edges.extend(list(its.permutations(room_indices, 2)))
            del room_indices
        else:
            room_indices = []
            for k in i['connected_locations']:
                room_indices.append(k)
            portal_index = portal_node_names.index(i['id'])
            portal_room_edges.extend(its.product([portal_index], room_indices))
            room_portal_edges.extend(its.product(room_indices, [portal_index]))
            room_edges.extend(list(its.permutations(room_indices, 2)))
            del room_indices
            del portal_index
            
    return room_node_names, room_edges

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
    from atomic.parsing.replayer import accumulate_files
    parser = argparse.ArgumentParser()
    parser.add_argument('adjacency_file', nargs=1, help='Adjacency file to use')
    parser.add_argument('fname', nargs='+', help='Log file(s) (or directory of CSV files) to process')
    parser.add_argument('-c', '--create', action='store_true', help='Create adjacency matrix from scratch')
    args = vars(parser.parse_args())

    if args['create']:
        adjacency = {}
        for fname in accumulate_files(args['fname']):
            extract_adjacency(fname, adjacency)
        for start, end_set in adjacency.items():
            print(start, sorted(end_set))
    else:
        adjacency_matrix = getSandRMap(fname=args['adjacency_file'][0])
        errors = set()
        for fname in accumulate_files(args['fname']):
            errors |= verify_adjacency(fname, adjacency_matrix)
        print(sorted(errors))
