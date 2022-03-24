#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Mar 11 15:40:39 2022

@author: mostafh
"""
from dateutil import parser
import pandas as pd

class ACWrapper:
    def __init__(self, team_name, ac_name):
        self.team_name = team_name
        self.name = ac_name
        self.messages = []
        self.start_time = 0
        self.score_names = []
        self.callsigns = ['green', 'red', 'blue']
        
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
        
        
        
