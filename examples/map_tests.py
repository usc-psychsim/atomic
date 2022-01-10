#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Sep 14 17:27:33 2021

@author: mostafh
"""

import json
ddir = '../data/ASU_DATA/'
fnameA = ddir + 'study-2_2021.06_HSRData_TrialMessages_Trial-T000421_Team-TM000111_Member-na_CondBtwn-2_CondWin-SaturnA_Vers-6.metadata'
fnameB = ddir + 'study-2_2021.06_HSRData_TrialMessages_Trial-T000401_Team-TM000101_Member-na_CondBtwn-2_CondWin-SaturnB_Vers-6.metadata'
 
def get_map(fname):
    jsonfile = open(fname, 'rt')    
    semantic_map = None
    for line in jsonfile.readlines():
        jmsg = json.loads(line)
        if 'semantic_map' in jmsg['data'].keys():
            semantic_map = jmsg['data']['semantic_map']
            break
    jsonfile.close()
    return semantic_map


def collect(fname, look_for):
    msgs = []
    jsonfile = open(fname, 'rt')    
    for line in jsonfile.readlines():
        jmsg = json.loads(line)
        ignore = False
        for k,v in look_for.items():
            if not ((k in jmsg['data'].keys()) and (jmsg['data'][k] == v)):
                ignore = True
                break
        if not ignore:
            msgs.append(jmsg)
    jsonfile.close()
    return msgs


def get_victims(fname):
    jsonfile = open(fname, 'rt')
    jsonMsgs = [json.loads(line) for line in jsonfile.readlines()]
    jsonfile.close()
    
    for jmsg in jsonMsgs:
        mtype = jmsg['msg']['sub_type']
        m = jmsg['data']
        if mtype == 'Mission:VictimList':
            return m['mission_victim_list']
    return None

#vicA = get_victims(fnameA)
vicB = get_victims(fnameB)

#
#mapA = get_map(fnameA)
#mapB = get_map(fnameB)
#
#mapBoth = json.load(open('../maps/Saturn/Saturn_1.5_3D_sm_v1.0.json','r'))
#
#for k,vA in mapA.items():
#    vB = mapB[k]
#    if vA != vB:
#        print('diff', k)
#    else:
#        print('same', k)
#        
#    if vA != mapBoth[k]:
#        print('diff both', k)
#    else:
#        print('same both', k)