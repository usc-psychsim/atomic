#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Mar 15 13:32:51 2022

@author: mostafh
"""

from .acwrapper import ACWrapper
import json
import pandas as pd
import numpy as np


class GelpWrapper(ACWrapper):
    """
    "Overall" leadership score: mean = 6.1, SD = 1.6. 
    Attribute leadership scores: 
    IDEAS: mean = 4.0, SD = 1.6. 
    FOCUS: mean = 4.2, SD = 1.3. 
    COORDINATE: mean = 4.6, SD = 1.1. 
    MONITOR: mean = 3.9, SD = 1.4. 
    SHARE: mean = 4.3, SD = 1.3. 
    PLAN: mean = 4.1, SD = 1.3. 
    AGREE: mean = 4.6, SD = 1.2. 
    HELP: mean = 4.8, SD = 1.2.
    """

    def __init__(self, agent_name, world=None, **kwargs):
        super().__init__(agent_name, world, **kwargs)
        self.score_names = ['Ideas', 'Focus', 'Coordinate', 'Monitor', 'Share', 'Plan', 'Agree', 'Help', 'Leadership'] 
        self.topic_handlers = {
            'trial': self.handle_trial,
            'agent/gelp': self.handle_msg}

        self.data = pd.DataFrame()
        
    def handle_msg(self, message, data, mission_time):
        new_data = []
        i = 0
        for result in data.get('gelp_results', {}):
            i += 1
            record = self.world.make_record({self.score_names[i]: value for i, value in enumerate(result['gelp_components'])})
            record['Player'] = result['callsign']
            record[self.score_names[-1]] = result['gelp_overall']
            new_data.append(record)
        if new_data:
            self.last = pd.DataFrame(new_data)
            self.data = pd.concat([self.data, self.last], ignore_index=True)
        return new_data
    

class GOLDWrapper(ACWrapper):
    def __init__(self, team_name, world=None, **kwargs):
        super().__init__(team_name, world, **kwargs)
        self.topic_handlers = {
            'trial': self.handle_trial,
            'agent/gold': self.handle_msg}

        self.data = pd.DataFrame()

    def handle_msg(self, message, data, mission_time):
        if data['gold_results']:
            print(data)
