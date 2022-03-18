#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Mar 11 15:40:39 2022

@author: mostafh
"""
from dateutil import parser


class ACWrapper:
    def __init__(self, team_name, ac_name):
        self.team_name = team_name
        self.name = ac_name
        self.messages = []
        self.start_time = 0
        
    def handle_message(self, topic, message, data):
        if topic not in self.topic_handlers:
            return

        self.topic_handlers[topic](message, data) 
        self.messages.append(data)
        
        
    def handle_trial(self, message, data):
        self.start_time = parser.parse(message['timestamp'])
        
    def elapsed_millis(self, message):
        time_diff = parser.parse(message['timestamp']) - self.start_time
        milliseconds = 1000*time_diff.seconds + time_diff.microseconds/1000
        return milliseconds
        
        
        
