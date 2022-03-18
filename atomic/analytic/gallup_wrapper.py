#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Mar 15 13:32:51 2022

@author: mostafh
"""

from .acwrapper import ACWrapper
import pandas as pd
import numpy as np

class GComp:
    Num_Components = 8
    [Ideas, Focus, Coordinate, Monitor, Share, Plan, Agree, Help] = list(range(Num_Components))


class GelpWrapper(ACWrapper):
    def __init__(self, team_name, ac_name):
        super().__init__(team_name, ac_name)
        self.callsigns = ['Green', 'Red', 'Blue']
        self.comp_data = [pd.DataFrame(columns=['millis'] + self.callsigns) for i in range(GComp.Num_Components)]
        self.overall_data = pd.DataFrame(columns=['millis'] + self.callsigns)
        self.topic_handlers = {
            'trial': self.handle_trial,
            'agent/gelp': self.handle_msg}

        
    def handle_msg(self, message, data):
        comp_results = {r['callsign']:r['gelp_components'] for r in data['gelp_results']}
        for gcomponent in range(GComp.Num_Components):
            row = [comp_results.get(callsign, np.zeros(GComp.Num_Components))[gcomponent] for callsign in self.callsigns]
            self.comp_data[gcomponent].loc[len(self.comp_data[gcomponent])] = [self.elapsed_millis(message)] + row
            
        
        overall_results = {r['callsign']:r['gelp_overall'] for r in data['gelp_results']}
        self.overall_data.loc[len(self.overall_data)] = [self.elapsed_millis(message)] + \
                                        [overall_results.get(callsign, 0) for callsign in self.callsigns]