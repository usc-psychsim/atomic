#!/usr/bin/env python3

import csv
import json
import sys

# extracts victim info from csv file & adds to existing 
# json semantic map
# INPUT: csvfile
#   ./csv_2_json_victims.py

victims_file = '../saturn/MapBlocks_SaturnB_Mission_2.csv'
map_file = '../saturn/Saturn_1.0_sm.json'

orig_map = json.load(open(map_file,'r'))
orig_locations = orig_map[u'locations']
orig_connections = orig_map[u'connections']
orig_objs = orig_map[u'objects']

root_name = map_file.split('.json')[0]
new_map_fname = root_name+"_with_victimsB.json"
new_mapfile = open(new_map_fname,'w')
print('new map name is '+new_map_fname)

# load whole thing as json then write out once victims added to objects existing json objects

victims = []
mfile = open(new_map_fname, 'rt')
victim_data = {}
new_locs = {}
new_conns = {}
#victim_data['objects'] = []
victim_data['objects'] = orig_objs
new_locs['locations'] = orig_locations
new_conns['connections'] = orig_connections

with open(victims_file) as csv_file:
    csv_reader = csv.reader(csv_file, delimiter=',')
    line_count = 0
    for row in csv_reader:
        if line_count == 0 or row[5] == 'Rubble':
            line_count += 1
        else:
            xyz = row[0].split(' ')
            vtype = row[1]
            color = 'vg'+str(line_count)
            vdicttype = 'green_victim'
            if vtype.find('victim') > -1:
                if vtype.find('2') > -1:
                    color = 'vy'+str(line_count)
                    vdicttype = 'yellow_victim'

            victim_data['objects'].append({
            #orig_objs.append({
            "id":color,
            "type": vdicttype,
            "bounds": {
                "type" : "block",
                "coordinates": [
                    {
                        "x": xyz[0], 
                        "z": xyz[2]
                        }
                    ]
                }
            })
            line_count += 1

    json.dump(new_locs,new_mapfile,indent=True)
    json.dump(new_conns,new_mapfile,indent=True)
    json.dump(victim_data,new_mapfile,indent=True)

