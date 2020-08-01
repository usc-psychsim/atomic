#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jul 26 12:56:43 2020

@author: RTRC
"""
import os.path
from os import listdir
import pandas as pd
import numpy as np

cols = ['file', 'player', 'duration', \
        'success', 'failed', \
        'savedGold', 'savedGreenBe4', 'savedGreenAft',\
        'rooms', 'moves']
stats = pd.DataFrame(columns = cols)
roomStats  = pd.DataFrame()
k = 0
halftime = 60 * 5

fpath = os.path.join(os.path.dirname(__file__),'data')
files = [f for f in listdir(fpath) if f.startswith('processed_ASIST')]

roomVisitSeqs = {}
for fl in files[:]:
    data = pd.read_csv(os.path.join(fpath, fl))
    stats.loc[k, 'file'] = fl
    stats.loc[k, 'player'] = data['player_ID'].iloc[0]
    print('---', fl, stats.loc[k, 'player'])
              
    print('Number of rows', len(data))
    
    data = data.dropna(axis=0, subset=['Room_in'])
     
    # Remove in_progress rows that were never back-filled
    data= data.loc[data['triage_result']!='IN_PROGRESS',:]
    print('Number of rows after triage in progress removal', len(data))
    
    # Remove triage_in_progress rows where victim being triaged different from victim in CH
    triageOn = data['triage_in_progress'] == True
    sameVic = data['event_triage_victim_id']==data['victim_in_crosshair_id']
    data= data.loc[~triageOn | sameVic,:]
    print('Number of rows after inconsistent triage vic and CH removal', len(data))
    
    # Rempve 'd' or 'x' at the end of room names
    rooms = [str(loc) for loc in data['Room_in'].unique()]
    newRooms = {r:r for r in rooms if not (r.endswith('x') or r.endswith('d'))}
    newRooms.update({r:r[:-1] for r in rooms if r.endswith('x') or r.endswith('d')})
    data['Room_in'].replace(newRooms, inplace=True)
    rooms = [str(loc) for loc in data['Room_in'].unique()]
    stats.loc[k, 'rooms'] = len(rooms)
            
    # Duration of play
    data['dtime'] = pd.to_datetime(data['@timestamp'], infer_datetime_format=True, exact=False)
    stats.loc[k, 'duration'] = (data['dtime'].values[-1] - data['dtime'].values[0]) / np.timedelta64(1, 's')
    
    # Seconds into the game
    startTime = data['dtime'].iloc[0]
    data['seconds'] = round((data['dtime'] - startTime) / np.timedelta64(1, 's'))    
    data.set_index('dtime', inplace=True)
    
    # Count of failed triages
    triageStatus = data[['seconds', 'triage_result']]
    triageStatus = triageStatus.loc[triageStatus['triage_result'].shift() != triageStatus['triage_result']]
    stats.loc[k, 'failed'] = len(triageStatus.loc[triageStatus['triage_result'] == 'UNSUCCESSFUL'])
       
    # Room visits. Must include None rooms to calculate dwell times correctly
    roomVisits = data[['seconds', 'Room_in']]
    roomVisits = roomVisits.loc[roomVisits['Room_in'].shift() != roomVisits['Room_in']]
    roomVisits['dur'] = - roomVisits['seconds'].diff(periods=-1)
    stats.loc[k, 'moves'] = len(roomVisits)
    roomVisits.dropna(inplace=True, axis=0)
    # Total dwell time in each room
    dwell = roomVisits.groupby('Room_in').sum()
    
    roomStats[fl] = dwell['dur']
        
    ### Saved victims stats
    vics = data.loc[data['triage_result'] == 'SUCCESSFUL', \
                    ['seconds', 'event_triage_victim_id','victim_in_cross_hair_color', 'triage_result']] 
    vics = vics.loc[vics['event_triage_victim_id'].shift() != vics['event_triage_victim_id']]
    stats.loc[k, 'savedGold'] = len(vics.loc[vics['victim_in_cross_hair_color'] == 'Gold'])
    stats.loc[k, 'savedGreenBe4'] = len(vics.loc[(vics['victim_in_cross_hair_color'] == 'Green') & (vics['seconds'] <= halftime)])
    stats.loc[k, 'savedGreenAft'] = len(vics.loc[(vics['victim_in_cross_hair_color'] == 'Green') & (vics['seconds'] > halftime)])
    
    k = k + 1
    
    roomVisitSeqs[fl] = roomVisits

stats['success'] = stats['savedGold'] + stats['savedGreenBe4'] + stats['savedGreenAft']    
roomStats.fillna(0, inplace=True)