#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Mar 11 15:40:39 2022

@author: mostafh
"""
from dateutil import parser
import pandas as pd
import numpy as np


class ACWrapper:
    def __init__(self, team_name, ac_name):
        self.team_name = team_name
        self.ac_name = ac_name
        self.messages = []
        self.start_time = 0
        self.score_names = []
        self.callsigns = ['green', 'red', 'blue']
        self.data = []
        
    @property
    def name(self):
        return self.team_name + ':' + self.ac_name
        
    def make_dfs(self):
        self.data = [pd.DataFrame(columns=['millis'] + self.callsigns) for i in range(len(self.score_names))]
        
    def n_scores(self):
        return len(self.score_names)
        
    def handle_message(self, topic, message, data):
        if topic not in self.topic_handlers:
            return

        self.topic_handlers[topic](message, data) 
        self.messages.append([message, data])
        
    def handle_trial(self, message, data):
        self.start_time = parser.parse(message['timestamp'])
        
    def elapsed_millis(self, message):
        time_diff = parser.parse(message['timestamp']) - self.start_time
        milliseconds = 1000*time_diff.seconds + time_diff.microseconds/1000
        return milliseconds
        
    ''' Compare players over the last history_sec seconds
        For each score, return a list of [min, max] of the players that fall well below/above 
        the others on this score.
    '''
    def compare(self, history_sec):
        start_ms = self.elapsed_millis(self.messages[-1][0]) - history_sec*1000
        extremes = {score:['', ''] for score in self.score_names}
        for si, score in enumerate(self.score_names):
            df = self.data[si]
            relevant_df = df.loc[df['millis'] >= start_ms, :]
            means = relevant_df.mean()
            stds = relevant_df.std()
            for callsign in self.callsigns:
                thiscall_ub = means[callsign] + stds[callsign]
                thiscall_lb = means[callsign] - stds[callsign]
                if np.all([thiscall_ub <= means[other]-stds[other] for other in self.callsigns]):
                    extremes[score][0] = callsign
                if np.all([thiscall_lb >= means[other]+stds[other] for other in self.callsigns]):
                    extremes[score][1] = callsign
                    
        return extremes
