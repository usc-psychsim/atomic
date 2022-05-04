#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Mar 11 15:40:39 2022

@author: mostafh
"""
from dateutil import parser
import pandas as pd
import numpy as np

from psychsim.pwl.keys import stateKey, binaryKey
from psychsim.action import Action, ActionSet


class ACWrapper:
    def __init__(self, agent_name, world=None, **kwargs):
        self.name = agent_name

        self.messages = []
        self.start_time = 0
        self.score_names = []
        self.callsigns = ['green', 'red', 'blue']
        self.trial = None
        self.data = None
        self.last = None
        self.topic_handlers = {}
        self.ignored_topics = set()

        self.variables = kwargs.get('variables', {})
        self.influences = {}
        self.team_agent = None
        self.asi = None

        self.world = world

    def handle_message(self, msg, mission_time=None):
        msg_topic = msg.get('topic', '')
        try:
            handler = self.topic_handlers[msg_topic]
        except KeyError:
            data = []
        else:
            data = handler(msg['msg'], msg['data'], 
                           None if mission_time is None else (15*60)-(mission_time[0]*60+mission_time[1]))
        # add_joint_activity(world, world.agents[data['participant_id']], team.name, data['jag'])
        return self.compute_state_delta(data)

    def compute_state_delta(self, data):
        state_delta = {}
        if data:
            for record in data:
                for field in record.keys() & self.variables.keys():
                    if self.variables[field]['object'] == 'player':
                        var = self.get_player_variable(record['Player'], field)
                    elif self.variables[field]['object'] == 'team':
                        var = self.get_team_variable(field)
                    else:
                        raise ValueError(f'Unable to create variable for {field}')
                    if not isinstance(record[field], self.variables[field]['values']):
                        if self.variables[field]['values'] is bool:
                            record[field] = record[field] > self.variables[field]['threshold']
                        else:
                            raise TypeError(f'Unable to coerce type for {field}')
                    state_delta[var] = record[field]
        return state_delta        
        
    def make_dfs(self):
        self.data = [pd.DataFrame(columns=['millis'] + self.callsigns) for i in range(len(self.score_names))]
        
    def n_scores(self):
        return len(self.score_names)
        
    def ignore_msg(self, message, data, mission_time):
        return []

    def handle_trial(self, message, data, mission_time):
        self.start_time = parser.parse(message['timestamp'])
        self.trial = data['trial_number']

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

    def get_effects(self, intervention):
        """
        :return: any effects on this AC's variables by the given intervention
        """
        if isinstance(intervention, Action) or isinstance(intervention, ActionSet):
            intervention = intervention['verb']
        return {var: table['effects'][intervention] for var, table in self.variables.items() 
                if 'effects' in table and intervention in table['effects']}

    def get_field(self, field):
        return {var: table[field] for var, table in self.variables.items()
                if field in table}    

    def get_ASI_reward(self):
        return self.get_field('ASI reward')

    def get_conditions(self):
        return self.get_field('condition')

    def get_player_variable(self, player, var_name):
        return stateKey(player, f'{self.name} {var_name}')

    def get_pair_variable(self, player1, player2, var_name):
        return binaryKey(player1, player2, f'{self.name} {var_name}')

    def get_team_variable(self, var_name):
        return stateKey(self.team_agent.name, f'{self.name} {var_name}')

    def define_variable(self, world, key, table):
        if isinstance(table['values'], list):
            world.defineVariable(key, list, lo=table['values'])
            world.setFeature(key, table['values'][0])
        elif table['values'] is int:
            world.defineVariable(key, int, lo=0, hi=table.get('hi', None))
            world.setFeature(key, 0)
        elif table['values'] is bool:
            world.defineVariable(key, bool)
            world.setFeature(key, True)
        elif table['values'] is float:
            world.defineVariable(key, float)
            world.setFeature(key, 0.)
        else:
            raise TypeError(f'Unable to create variable {key} of type {table["values"].__name__}')
        self.influences[key] = table.get('influences', {})

    def augment_world(self, world, team_agent, players):
        """
        :type team_agent: Agent
        :type players: dict(str->Agent)
        """
        self.team_agent = team_agent
        for var_name, table in self.variables.items():
            if 'object' not in table:
                self.logger.warning(f'No player/pair/team specification for variable {var_name} in AC {self.name}')
            elif table['object'] == 'player':
                # Player-specific variables
                for player in players:
                    key = self.get_player_variable(player, var_name)
                    self.define_variable(world, key, table)
            elif table['object'] == 'pair':
                # Pairwise variables
                for player in players:
                    for other in players:
                        if other != player:
                            key = self.get_pair_variable(player, other, var_name)
                            if var_name in world.relations:
                                world.relations[var_name][key] = {'subject': player, 'object': other}
                            else:
                                world.relations[var_name] = {key: {'subject': player, 'object': other}}
                            self.define_variable(world, key, table)
            elif table['object'] == 'team':
                # Team-wide variables
                key = self.get_team_variable(var_name)
                self.define_variable(world, key, table)
