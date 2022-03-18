#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Mar 17 10:30:43 2022

@author: mostafh
"""
import traceback

from atomic.analytic.models.joint_activity_model import JointActivityModel
from atomic.analytic.models.jags import asist_jags as aj

from atomic.analytic.models.player import Player
from atomic.analytic.acwrapper import ACWrapper

class JAGWrapper(ACWrapper):
    def __init__(self, team_name, ac_name):
        super().__init__(team_name, ac_name)
        

        self.topic_handlers = {
            'trial': self.handle_trial,
            'observations/events/player/jag': self.handle_jag,
            'observations/events/mission': self.handle_mission,
            'observations/events/player/role_selected': self.handle_role
        }
        print('inited')
        self.players = {}
        self.elapsed_milliseconds = 0
        self.started = False
        self.asi_jam = JointActivityModel(aj.ASIST_JAGS)
        self.process_later = []

    def handle_trial(self, message, data):
        players = {}
        for client in data['client_info']:
            players[client['participant_id']] = Player(client)
        self.players.update(players)
        super().handle_trial(message, data)

    def handle_mission(self, message, data):
        self.elapsed_milliseconds = data['elapsed_milliseconds']
        state = data['mission_state']
        if state == 'Start':
            self.started = True
        if state == 'Stop':
            self.started = False

    def handle_role(self, message, data):
        player_id = data['participant_id']
        role = data['new_role']
        player = self.players[player_id]
        player.set_role(role)
        
    def all_players_jag_ids(self):
        for pid in self.players.keys():
            self.player_jag_ids(pid)
            
                
    def player_jag_ids(self, player_id):
        for jag in self.players[player_id].joint_activity_model.jag_instances:
            if jag.urn == 'urn:ihmc:asist:search-area':
                continue
            print(player_id, jag.to_string())
            
        
    def print_asi_jam(self):
        for jag in self.asi_jam.jag_instances:
            if jag.urn == 'urn:ihmc:asist:search-area':
                continue
            print(jag.to_string())

    ''' Look back at messages that were received prematurely
        if you find this uid, process them
    '''
    def look_back(self, uid):
        indices = [i for i in range(len(self.process_later)) if self.process_later[i][0] == uid]
        for i in indices:
            self.handle_jag(self.process_later[i][1], self.process_later[i][2])
            
        if len(indices) > 0:
            print('==handled arears', len(indices))
        self.process_later = [self.process_later[i] for i in range(len(self.process_later)) if i not in indices]

    def handle_jag(self, message, data):
        try:
            if message['sub_type'] == 'Event:Discovered':
                player_id = data['participant_id']
                player = self.players[player_id]
                instance_description = data['jag']
                jag = player.joint_activity_model.create_from_instance(instance_description)
                
                ## The fact that a certain player discovered it doesn't mean it's news to the ASI
                ## Only create a new ASI JAG if ASI doesn't already knows about this
                urn = instance_description['urn']
                inputs = instance_description['inputs']
                if self.asi_jam.get(urn, inputs) is None:
                    self.asi_jam.create_from_instance(instance_description)
    #            print("discovered " + jag.short_string(), jag.id, 'for', player_id)
                self.look_back(jag.id)
                return
    
            observer_player_id = data['participant_id']
            observer_callsign = self.players[observer_player_id].callsign.lower()
            player = self.players[observer_player_id]
            instance_update = data['jag']
            uid = instance_update['id']
            elapsed_ms = instance_update['elapsed_milliseconds'] 
            self.__elapsed_milliseconds = elapsed_ms       
            jag_instance = player.joint_activity_model.get_by_id(uid)
            if jag_instance is None:
                self.process_later.append([uid, message, data])
                return
            asi_jag_instance = self.asi_jam.get_by_urn_recursive(jag_instance.urn, jag_instance.inputs, jag_instance.outputs)
            if asi_jag_instance is None:
                print('oh no')
    
#            print(message['sub_type'], observer_player_id, uid, instance_update.get('urn', ''), elapsed_ms)        
                
            if message['sub_type'] == 'Event:Awareness':
                # self.logger.info(jag_instance.short_string() + " awareness " + str(awareness))
                awareness = instance_update['awareness']
                for aware_player_id in awareness.keys():
                    callsign = self.players[aware_player_id].callsign.lower()
                    jag_instance.update_awareness(observer_callsign, callsign, awareness[aware_player_id], elapsed_ms)
                    asi_jag_instance.update_awareness(observer_callsign, callsign, awareness[aware_player_id], elapsed_ms)
                    
            elif message['sub_type'] == 'Event:Addressing':                
                addressing = instance_update['addressing']
                for addressing_player_id in addressing.keys():
                    callsign = self.players[addressing_player_id].callsign.lower()
                    jag_instance.update_addressing(observer_callsign, callsign, addressing[addressing_player_id], elapsed_ms)
                    asi_jag_instance.update_addressing(observer_callsign, callsign, addressing[addressing_player_id], elapsed_ms)
#                    if addressing[addressing_player_id] > 0:
#                        print('-----------', jag_instance.urn, jag_instance.inputs, addressing_player_id, addressing[addressing_player_id])
#                        self.print_asi_jam()
            
            elif message['sub_type'] == 'Event:Preparing':  
                preparing = instance_update['preparing']
                for preparing_player_id in preparing.keys():
                    callsign = self.players[preparing_player_id].callsign.lower()
                    # update preparing based on last activity
                    if preparing[preparing_player_id] > 0.0:
                        jag_instance.update_preparing(observer_callsign, callsign, preparing[preparing_player_id], elapsed_ms)
                        asi_jag_instance.update_preparing(observer_callsign, callsign, preparing[preparing_player_id], elapsed_ms)
                
            elif message['sub_type'] == 'Event:Completion':
                completion_status = instance_update['is_complete']
                jag_instance.update_completion_status(observer_callsign, completion_status, elapsed_ms)
                asi_jag_instance.update_completion_status(observer_callsign, completion_status, elapsed_ms)
                print(jag_instance.short_string() + " completion_status " + str(completion_status) + ": " + str(elapsed_ms), observer_player_id)
            else:
                print('je ne sais pas quoi', data)
            
        except Exception:
            print(traceback.format_exc())
