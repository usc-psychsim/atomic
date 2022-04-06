#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Mar 17 10:30:43 2022

@author: mostafh
"""
import traceback
import pandas as pd

from atomic.analytic.models.joint_activity_model import JointActivityModel
from atomic.analytic.models.jags import asist_jags as aj
from .utils.jag_utils import merge_jags
from .models.jags.jag import Jag

from atomic.analytic.models.player import Player
from atomic.analytic.acwrapper import ACWrapper

class JAGWrapper(ACWrapper):
    def __init__(self, team_name, ac_name):
        super().__init__(team_name, ac_name)
        self.score_names = ["active_duration","joint_activity_efficiency","redundancy_ratio"]
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
        self.asi_completed_jags = []
        self.process_later = []
        self.data = pd.DataFrame(columns=['millis'] + self.score_names)
        common_tasks = [aj.AT_PROPER_TRIAGE_AREA, aj.CHECK_IF_UNLOCKED, aj.DROP_OFF_VICTIM, aj.PICK_UP_VICTIM,
                        aj.GET_IN_RANGE, aj.UNLOCK_VICTIM]
        self.role_to_urns = {clr:common_tasks for clr in ['red', 'blue', 'green']}
        self.role_to_urns['red'].extend([aj.STABILIZE, aj.DETERMINE_TRIAGE_AREA])
        self.role_to_urns = {k:[j['urn'] for j in v] for k,v in self.role_to_urns.items()}

    def handle_trial(self, message, data):
        if len(self.players) > 0:
            return
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
            if jag.urn != aj.RESCUE_VICTIM['urn']:
                continue
            print(player_id, jag.to_string())
            
        
    def print_asi_jam(self):
        for jag in self.asi_completed_jags:
            if jag.urn != aj.RESCUE_VICTIM['urn']:
                continue
            print(jag.to_string())

    ''' Look back at messages that were received prematurely
        if you find this uid, process them
    '''
    def look_back(self, uid):
        indices = [i for i in range(len(self.process_later)) if self.process_later[i][0] == uid]
        for i in indices:
            self.handle_jag(self.process_later[i][1], self.process_later[i][2])
            
        self.process_later = [self.process_later[i] for i in range(len(self.process_later)) if i not in indices]

    def handle_jag(self, message, data):
        try:
            if message['sub_type'] == 'Event:Discovered':
                player_id = data['participant_id']
                player = self.players[player_id]
                instance_description = data['jag']
                jag = player.joint_activity_model.create_from_instance(instance_description)                
#                if instance_description['urn'] == aj.RESCUE_VICTIM['urn']:
#                    print("discovered " + jag.short_string(), jag.id, 'for', player_id)
                ## In case messages arrived out of order
                if jag is None:
                    print('stop')
                self.look_back(jag.id)
                return

            if message['sub_type'] == 'Event:Summary':
                elapsed = [self.elapsed_millis(message)]
                self.data.loc[len(self.data)] = elapsed + [data.get(score, 0) for score in self.score_names]     
                return
                
            observer_player_id = data['participant_id']
            observer_callsign = self.players[observer_player_id].callsign.lower()
            player = self.players[observer_player_id]
            instance_update = data['jag']
            uid = instance_update['id']
            elapsed_ms = instance_update['elapsed_milliseconds'] 
            self.elapsed_milliseconds = elapsed_ms       
            if player.joint_activity_model is None:
                print('stop')
            jag_instance = player.joint_activity_model.get_by_id(uid)
            
            ## If messages arrive out of order, keep this one for later processing
            if jag_instance is None:
                self.process_later.append([uid, message, data])
                return
                
            if message['sub_type'] == 'Event:Awareness':
                # self.logger.info(jag_instance.short_string() + " awareness " + str(awareness))
                awareness = instance_update['awareness']
                for aware_player_id in awareness.keys():
                    callsign = self.players[aware_player_id].callsign.lower()
                    jag_instance.update_awareness(observer_callsign, callsign, awareness[aware_player_id], elapsed_ms)
                    
            elif message['sub_type'] == 'Event:Addressing':                
                addressing = instance_update['addressing']
                for addressing_player_id in addressing.keys():
                    callsign = self.players[addressing_player_id].callsign.lower()
                    jag_instance.update_addressing(observer_callsign, callsign, addressing[addressing_player_id], elapsed_ms)
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
                
            elif message['sub_type'] == 'Event:Completion':
                completion_status = instance_update['is_complete']
                jag_instance.update_completion_status(observer_callsign, completion_status, elapsed_ms)
                if jag_instance.urn == aj.MOVE_VICTIM_TO_TRIAGE_AREA['urn'] and jag_instance.is_complete():
                    self.compute_measure(jag_instance)
                    print(jag_instance.short_string())
#                    self.player_stats()
                
            else:
                print('je ne sais pas quoi', data)
            
        except Exception:
            print(traceback.format_exc()) 
            
#        if (len(self.messages) % 500) == 0:
#            self.team_summary()
            
    def player_stats(self):
        role_lookup = {'Red': 'medic',
              'Blue': 'engineer',
              'Green': 'transporter'}
        print('individually')
        self.__player_stats_from_jags(False)
        print('asi perspective')
        self.__player_stats_from_jags(True)        
            
            
    def __player_stats_from_jags(self, from_asi_perspective):
        pmap = {'P000464': 'green', 'P000465': 'blue', 'P000463': 'red'}
        for player_id in self.players.keys():
            leaves_dict = dict()
            color = pmap[player_id]
            if from_asi_perspective:
                jags = self.asi_completed_jags
            else:
                jags = self.players[player_id].joint_activity_model.jag_instances
                
            ## Collect the leaves of all jags, except those this player can't do (consult role_to_urns)
            for jag in jags:
                if jag.urn != aj.RESCUE_VICTIM['urn']:
                    continue
                iter_leaves = {l.short_string():l for l in jag.get_leaves() if l.urn in self.role_to_urns[color]}
                leaves_dict.update(iter_leaves)
                
            addressing = [l for l in leaves_dict.values() if color in l.get_addressing()]
            awareness = [l for l in leaves_dict.values() if color in l.get_awareness()]
            unawareness = [l for l in leaves_dict.values() if color not in l.get_awareness()]
            
            ## NOTE: you may be aware of something but not addressing it because you're waiting on a dependency
            print(color, 'addressing', len(addressing), 'aware', len(awareness), 'total', len(leaves_dict))
#            if color == 'green':
#                for l in addressing:
#                    print(l.short_string())
            for l in unawareness:
                print(l.short_string())
    
    def compute_measure(self, jag: Jag):
        instances: dict[str, str] = {}
        last_player_id = None
        new_asi_jag = None
        for player_id in self.players:
            last_player_id = player_id
            player = self.players[player_id]
            player_victim_jag = player.joint_activity_model.get(aj.RESCUE_VICTIM['urn'], jag.inputs, jag.outputs)
            if player_victim_jag is not None:
                instances[player_id] = player_victim_jag.id_string
                if new_asi_jag is None:
                    new_asi_jag = player_victim_jag
                else:
                    new_asi_jag = merge_jags(new_asi_jag, player_victim_jag)

        self.recheck_completion(new_asi_jag, last_player_id)
        self.asi_completed_jags.append(new_asi_jag)
#        estimate = merged_jag.estimated_completion_duration
#        active_duration = merged_jag.completion_duration()
#        non_overlapping_duration = merged_jag.completion_non_overlapping_duration()
#        man_hour_efficiency = non_overlapping_duration / active_duration
#        joint_activity_efficiency = estimate / active_duration

    # used to update completion status after merging jags
    def recheck_completion(self, jag: Jag, player_id):
        if jag.is_leaf:
            jag.update_completion_status(player_id, jag.is_complete(), jag.completion_time)
        else:
            for child in jag.children:
                self.recheck_completion(child, player_id)


    def __get_player_by_callsign(self, callsign):
        for player in self.players.values():
            if player.callsign.lower() == callsign.lower():
                return player
        return None

    def team_summary(self):
        print("Team summary...")
        # medic
        red_set = self.player_summary('red')
        # transport
        green_set = self.player_summary('green')
        # engineer
        blue_set = self.player_summary('blue')

        intersection_set = red_set.intersection(green_set).intersection(blue_set)
        self.print_summary("intersection", intersection_set)

        union_set = set()
        union_set = union_set.union(red_set)
        union_set = union_set.union(green_set)
        union_set = union_set.union(blue_set)
        self.print_summary("union", union_set)
        elapsed_minutes = self.elapsed_milliseconds / 1000 / 60
        victims_per_minute = len(union_set) / elapsed_minutes
        print("find rate = " + str(victims_per_minute) + " victims per minute")
        remaining_minutes = 15 - elapsed_minutes
        estimated_found = len(union_set) + (victims_per_minute * remaining_minutes)
        print("estimated total found = " + str(estimated_found))
        print("minutes remaining = " + str(remaining_minutes))

    def player_summary(self, callsign):
        player = self.__get_player_by_callsign(callsign)
        jags = player.joint_activity_model.get_known_victims()
        player_set = set()
        player_set.update(jags)
        set_label = str(player.callsign + " " + player.role)
        self.print_summary(set_label, player_set)
        return player_set

    @staticmethod
    def print_summary(set_label, jag_set):
        victim_set = set()
        critical_count = 0
        complete_count = 0
        active_count = 0
        for jag in jag_set:
            victim_set.add(jag.inputs['victim-id'])
            if jag.inputs['victim-type'] == 'critical':
                critical_count += 1
            if jag.is_complete():
                complete_count += 1
            if jag.is_active():
                active_count += 1

        print(str(set_label) + ": " + str(victim_set) + "   " +
              str(len(jag_set)) + " victims" +
              " (" + str(critical_count) + " critical/" + str(len(jag_set) - critical_count) + " regular)" +
              " (" + str(complete_count) + " complete/" + str(len(jag_set) - complete_count) + " incomplete)" +
              " (" + str(active_count) + " active/" + str(len(jag_set) - active_count) + " inactive)")

