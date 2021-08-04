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
import pandas as pd

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
                
    def __repr__(self):
        return '%s %s %s %s' %(self.psysim_name, self.msg_type, self.psysim_args, self.conditions)
        
    def get_psysim_name(self, msg):
        player = msg['playername']
        
        ## If msg is of the wrong type, no
        if msg['sub_type'] != self.msg_type:
            return None
        
        ## For each condition specified in the CSV
        for var, val in self.conditions.items():
            ## if the condition has a evaluation that depends on auxiliary data
            if '(' in val:
                column= val[:val.index('(')]
                row_key = val[val.index('(')+1 : val.index(')')]
                row_value = msg[row_key]
                if row_value not in Msg2ActionEntry.auxiliary_data.index:
#                    print('Condition not met', var, val, row_value, msg)
                    return None
                if msg[var] != Msg2ActionEntry.auxiliary_data.loc[row_value, column]:
#                    print('Condition not met', var, val, row_value, msg)
                    return None
            ## if the condition is simple 
            else:
                if msg[var] != val:
                    return None
                
        psyim_act_name = '(%s, %s' %(self.psysim_name, player)
        if len(self.psysim_args) > 0:
            psyim_act_name  = psyim_act_name + ', ' +   ', '.join( [msg[arg] for arg in self.psysim_args])
        psyim_act_name = psyim_act_name + ')'
        return psyim_act_name 
    
##################### CLASS METHODS    
    
    conversions = []
    auxiliary_data = None
    
    @classmethod
    def read_psysim_msg_conversion(cls, fname, aux_data_file=None):
        if aux_data_file is not None:
            Msg2ActionEntry.auxiliary_data = pd.read_csv(aux_data_file, index_col=0)
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

    @classmethod
    def get_msg_types(cls):
        mtypes = set()
        for conv in Msg2ActionEntry.conversions:
            mtypes.add(conv.msg_type)
        return mtypes
    
    
    @classmethod
    def print_all(cls):
        for conv in Msg2ActionEntry.conversions:
            print(conv)    
        