#!/usr/bin/env python

### The constructor lines you're looking for are in lines 53-57, 63-67 and 90-95. (from orig rddl_psim_real)

import argparse
import logging
import os.path
import sys
import numpy as np
import json

from rddl2psychsim.conversion.converter import Converter
from atomic.parsing.get_psychsim_action_name import Msg2ActionEntry
from atomic.parsing.parse_into_msg_qs import MsgQCreator

#### will need to be one object that we intantiate in atomic_parser

class atomicParser(object):
    def __init__(self):
        self.RDDL_FILE_TEMPLATE = ''
        ####################  J S O N   M S G   T O  P S Y C H S I M   A C T I O N   N A M E
        self.USE_COLLAPSED = True
        if self.USE_COLLAPSED:
            json_msg_action_lookup_fname = os.path.join(os.path.dirname(__file__), 'data', 'rddl_psim', 'rddl2actions_newpickup.csv')
            lookup_aux_data_fname = os.path.join(os.path.dirname(__file__), 'maps', 'Saturn', 'rddl_clpsd_neighbors.csv')
            self.RDDL_FILE_TEMPLATE = os.path.join(os.path.dirname(__file__), 'data', 'rddl_psim', 'newpickup_v1_novics')

    
        Msg2ActionEntry.read_psysim_msg_conversion(json_msg_action_lookup_fname, lookup_aux_data_fname)
        self.usable_msg_types = Msg2ActionEntry.get_msg_types() # use for determining subscriptions

        #################  R D D L  2  P S Y C H S I M    W O R L D
        logging.root.setLevel(logging.CRITICAL)
        logging.basicConfig(
            handlers=[logging.StreamHandler(sys.stdout)],
            format='%(message)s', level=logging.CRITICAL)

        ##################  M S G S
        self.derived_features = []
        self.RDDL_FILE = self.RDDL_FILE_TEMPLATE + '_v.rddl'
        # pass '' metadata_file name to generate 
        self.msg_qs = MsgQCreator('', logger=logging)

        # call to set semantic map from atomic_parser once object instantiated
        # if 'semantic_map' in jmsg['data'].keys():
        #msg_qs.jsonParser.semantic_map = jmsg['data']['semantic_map']
        
        # do the loop here so can swap in real msgs
        #msg_qs.jsonParser.process_json_file(metadata_file)
        self.msg_qs.allMTypes = set()
        self.msg_qs.jsonParser.reset()
    
    def proc_msg_test(self, msg):
        self.msg_qs.jsonParser.process_message(json.loads(msg))

    def proc_msg(self, msg):
        self.msg_qs.jsonParser.process_message(msg)

    def load_victims(self,msg):
        self.msg_qs.jsonParser.vList = self.msg_qs.jsonParser.make_victims_list(msg['data']['mission_victim_list'])
        
    def post_processing(self):
        self.msg_qs.startProcessing(self.derived_features, self.usable_msg_types) # did call proc_json_file, now does rest
        self.msg_qs.jsonParser.write_rddl_file(self.RDDL_FILE_TEMPLATE)
        conv = Converter()
        conv.convert_file(self.RDDL_FILE, verbose=False)

    def load_semantic_map_test(self, rawmsg):
        print("LOADING MAP.....")
        mmsg = json.loads(rawmsg)
        self.msg_qs.jsonParser.semantic_map = mmsg['data']['semantic_map']
        self.msg_qs.jsonParser.add_rooms_map_live(mmsg)

    def load_semantic_map(self, mmsg):
        self.msg_qs.jsonParser.semantic_map = mmsg
        self.msg_qs.jsonParser.add_rooms_map_live(mmsg)

##################  S T E P    T H R O U G H
## for local testing

if __name__ == '__main__':        
    aparser = atomicParser()
    metadata_file = '/home/ubuntu/HSRData_TrialMessages_Trial-T000408_Team-TM000104_Member-na_CondBtwn-1_CondWin-SaturnB_Vers-8.metadata'
    jsonfile = open(metadata_file, 'rt')
    for line in jsonfile.readlines():
        if line.find('semantic_map') > -1:
            aparser.load_semantic_map_test(line)
        elif line.find('mission_victim_list') > -1:
            aparser.load_victims(json.loads(line))
        else:
            aparser.proc_msg_test(line)
    jsonfile.close()
    print('len vlist:: '+str(len(aparser.msg_qs.jsonParser.vList)))
    aparser.post_processing()
    print("chat msg == "+str(aparser.msg_qs.jsonParser.chat_msg))   
