#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat May 15 20:48:25 2021

@author: mostafh
"""
'''
Each Msg2ActionEntry object stores information needed to determine the name of the psychsim action than should be generated
when this message is encountered on the message bus.

The class has a static method thar reads in a conversion file and another static method that takes a testbed message and 
returns the psychsim action name (with a player argument and any others if specified in the conversion file).
'''
import csv


class Msg2ActionEntry:
    def __init__(self, psysim_name, psysim_args, msg_type, conditions):
        self.psysim_name = psysim_name
        self.msg_type = msg_type
        self.psysim_args = []
        self.conditions = {}
        if len(psysim_args) > 0:
            self.psysim_args = [arg.strip() for arg in psysim_args.split(',')]
        if len(conditions) > 0:
            conds = conditions.split(',')
            for cond in conds:
                [var, val] = cond.split('=')
                self.conditions[var.strip()] = val.strip()
        
    def get_psysim_name(self, msg):
        player = msg['playername']
        if msg['sub_type'] != self.msg_type:
            return None
        for var, val in self.conditions.items():
            if msg[var] != val:
                return None
        psyim_act_name = '(%s, %s' %(self.psysim_name, player)
        if len(self.psysim_args) > 0:
            psyim_act_name  = psyim_act_name + ', ' +   ', '.join( [msg[arg] for arg in self.psysim_args])
        psyim_act_name = psyim_act_name + ')'
        return psyim_act_name 
    
    conversions = []
    @classmethod
    def read_psysim_msg_conversion(cls, fname):
        with open(fname, newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                conversion = Msg2ActionEntry(row['psysim'], row['args'], row['msg_type'], row['conditions'])            
                Msg2ActionEntry.conversions.append(conversion)
                

    @classmethod    
    def get_action(cls, msg):
        for conv in Msg2ActionEntry.conversions:
            ret = conv.get_psysim_name(msg)
            if ret is not None:
                return ret
            
        return None
