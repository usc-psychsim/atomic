#!/usr/bin/env python3

import csv
import json
import sys

# extracts room & door info from a json semantic map 
# writes to csv file (for use with atomic/message_reader.py)
# INPUT: semantic map json file:
#   ./json_2_csv_rooms.py <json file>

# TODO: merge with message parser, skip csv writeout

locations_file = sys.argv[1]
root_name = locations_file.split('.json')[0]
room_csv_file = open(root_name+"_rooms.csv", "w")
door_csv_file = open(root_name+"_doors.csv", "w")

rooms = []
doors = []
victims = []
jsonfile = open(locations_file, 'rt')
alldat = json.load(jsonfile)
jsonfile.close()
allobjects = alldat[u'objects']
allrooms = alldat[u'locations']
alldoors = alldat[u'connections']
roomcnt = 0
doorcnt = 0
room_types = ['hallway','hallway_part','bathroom_part', 'room_part']

for r in allrooms:
    if r['type'] in room_types or (r['type'] == 'room' and 'child_locations' not in r):
        roomcnt += 1
        if 'bounds' in r:
            coords = r['bounds']
            fullxz = coords['coordinates']
            xz1 = fullxz[0]
            xz2 = fullxz[1]
            roomstr = str(r['id'])+", "+str(xz1['x'])+","+str(xz1['z'])+","+str(xz2['x'])+","+str(xz2['z'])
            rooms.append(roomstr)
for d in alldoors:
        doorcnt += 1
        coords = d['bounds']
        fullxz = coords['coordinates']
        xz1 = fullxz[0]
        xz2 = fullxz[1]
        r1 = d['connected_locations'][0]
        r2 = d['connected_locations'][1]
        doorstr = str(d['id'])+","+str(xz1['x'])+","+str(xz1['z'])+","+str(xz2['x'])+","+str(xz2['z'])+","+str(r1)+","+str(r2)
        doors.append(doorstr)

print("num rooms = "+str(roomcnt)+" num doors = "+str(doorcnt))

room_csv_file.write('RoomID,x0,z0,x1,z1\n')
for r in rooms:
    room_csv_file.write(str(r)+"\n")

door_csv_file.write('Index,x0,z0,x1,z1,Room0,Room1\n')
for d in doors:
    door_csv_file.write(str(d)+"\n")
room_csv_file.close()
door_csv_file.close()

