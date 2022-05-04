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

from psychsim.pwl.plane import equalRow
from psychsim.pwl.matrix import setToConstantMatrix
from psychsim.pwl.tree import makeTree
from psychsim.reward import maximizeFeature


class JAGWrapper(ACWrapper):
    def __init__(self, agent_name, world=None, **kwargs):
        super().__init__(agent_name, world, **kwargs)
        self.score_names = ["active_duration", "joint_activity_efficiency", "redundancy_ratio"]
        self.topic_handlers = {
            'trial': self.handle_trial,
            'observations/events/player/jag': self.handle_jag,
            'observations/events/mission': self.handle_mission,
            'observations/events/player/role_selected': self.handle_role
        }
        self.players = {}
        self.elapsed_milliseconds = 0
        self.started = False
        self.asi_completed_jags = []
        self.orphan_msgs = []
        self.data = pd.DataFrame(columns=['millis'] + self.score_names)
        common_tasks = [aj.AT_PROPER_TRIAGE_AREA, aj.CHECK_IF_UNLOCKED, aj.DROP_OFF_VICTIM, aj.PICK_UP_VICTIM,
                        aj.GET_IN_RANGE, aj.UNLOCK_VICTIM]
        self.role_to_urns = {clr: common_tasks for clr in ['red', 'blue', 'green']}
        self.role_to_urns['red'].extend([aj.STABILIZE, aj.DETERMINE_TRIAGE_AREA])
        self.role_to_urns = {k: [j['urn'] for j in v] for k,v in self.role_to_urns.items()}
        
        self.debug_discover = []

    def all_players_jag_ids(self):
        for pid in self.players.keys():
            self.player_jag_ids(pid)
            
    def player_jag_ids(self, player_id, short=True):
        for jag in self.players[player_id].joint_activity_model.jag_instances:
            if jag.urn != aj.RESCUE_VICTIM['urn']:
                continue
            if short:
                s = jag.short_string()
            else:
                s = jag.to_string()
            # print(player_id, s)
            
    def print_asi_jam(self, short=True):
        for jag in self.asi_completed_jags:
            if jag.urn != aj.RESCUE_VICTIM['urn']:
                continue
            if short:
                s = jag.short_string()
            else:
                s = jag.to_string()
            # print(s)

    ''' Look back at messages that were received prematurely
        if you find this uid, process them
    '''
    def look_back(self, uid):
        indices = [i for i in range(len(self.orphan_msgs)) if self.orphan_msgs[i][0] == uid]
        for i in indices:
            self.handle_jag(self.orphan_msgs[i][1], self.orphan_msgs[i][2], None)
            
        self.orphan_msgs = [self.orphan_msgs[i] for i in range(len(self.orphan_msgs)) if i not in indices]

    ########################################
    ########################################
    ######### Start of IHMC code copied from src/agents/joint_activity_client.py
    ######### Code was copied as-is except for lines indicated as such
    ########################################
    ########################################

    def handle_trial(self, message, data, mission_time):
        if len(self.players) > 0:
            return
        players = {}
        for client in data['client_info']:
                
            ########################################
            ######### USC addition
            ########################################
            if len(client['callsign']) == 0:
                continue
            
            players[client['participant_id']] = Player(client)
        self.players.update(players)
        super().handle_trial(message, data, mission_time)

    def handle_mission(self, message, data, mission_time):
        self.elapsed_milliseconds = data['elapsed_milliseconds']
        state = data['mission_state']
        if state == 'Start':
            self.started = True
        if state == 'Stop':
            self.started = False

    def handle_role(self, message, data, mission_time):
        player_id = data['participant_id']
        role = data['new_role']
        player = self.players[player_id]
        player.set_role(role)
        return []
        
    def handle_jag(self, message, data, mission_time):
        jid = data['jag'].get('id', '')
        if jid == 'b35361d2-ee24-4a43-a3e5-c1a43afa9f7a':
            print('+++++++++', message['sub_type'], data)
#        
        try:
            if message['sub_type'] == 'Event:Discovered':
                player_id = data['participant_id']
                player = self.players[player_id]
                instance_description = data['jag']
                jag = player.joint_activity_model.create_from_instance(instance_description)
                self.debug_discover.append(jag)
#                print("discovered " + jag.short_string())
                
                ########################################
                ######### USC addition
                ########################################
                self.look_back(jag.id)
                if self.world:
                    add_joint_activity(self.world, player, jag)
                
            elif message['sub_type'] == 'Event:Awareness':
                observer_player_id = data['participant_id']
                player = self.players[observer_player_id]
                instance_update = data['jag']
                uid = instance_update['id']
                jag_instance = player.joint_activity_model.get_by_id(uid)
                
                ########################################
                ######### USC addition
                ########################################
                if jag_instance is None: 
                    self.orphan_msgs.append([uid, message, data])
                    return
                
                awareness = instance_update['awareness']
                # print(jag_instance.short_string() + " awareness " + str(awareness))
                elapsed_ms = instance_update['elapsed_milliseconds']
                self.elapsed_milliseconds = elapsed_ms
                observer_callsign = self.players[observer_player_id].callsign.lower()
                for aware_player_id in awareness.keys():
                    callsign = self.players[aware_player_id].callsign.lower()
                    jag_instance.update_awareness(observer_callsign, callsign, awareness[aware_player_id], elapsed_ms)
            elif message['sub_type'] == 'Event:Preparing':
                # update individual
                observer_player_id = data['participant_id']
                player = self.players[observer_player_id]
                instance_update = data['jag']
                uid = instance_update['id']
                jag_instance = player.joint_activity_model.get_by_id(uid)
                
                ########################################
                ######### USC addition
                ########################################
                if jag_instance is None: 
                    self.orphan_msgs.append([uid, message, data])
                    return                
                
                preparing = instance_update['preparing']
                # print(jag_instance.short_string() + " preparing " + str(preparing))
                elapsed_ms = instance_update['elapsed_milliseconds']
                self.elapsed_milliseconds = elapsed_ms
                observer_callsign = self.players[observer_player_id].callsign.lower()
                for preparing_player_id in preparing.keys():
                    callsign = self.players[preparing_player_id].callsign.lower()
                    # update preparing based on last activity
                    if preparing[preparing_player_id] > 0.0:
                        jag_instance.update_preparing(observer_callsign, callsign, preparing[preparing_player_id], elapsed_ms)
                        
            elif message['sub_type'] == 'Event:Addressing':
                # update individual
                observer_player_id = data['participant_id']
                player = self.players[observer_player_id]
                instance_update = data['jag']
                uid = instance_update['id']
                jag_instance = player.joint_activity_model.get_by_id(uid)
                
                ########################################
                ######### USC addition
                ########################################
                if jag_instance is None: 
                    self.orphan_msgs.append([uid, message, data])
                    return
                
                addressing = instance_update['addressing']
                # print(jag_instance.short_string() + " addressing " + str(addressing))
                elapsed_ms = instance_update['elapsed_milliseconds']
                self.elapsed_milliseconds = elapsed_ms
                observer_callsign = self.players[observer_player_id].callsign.lower()
                for preparing_player_id in addressing.keys():
                    callsign = self.players[preparing_player_id].callsign.lower()
                    # update preparing based on last activity
                    if addressing[preparing_player_id] > 0.0:
                        if player.last_activity_completed is None:
#                            if callsign not in jag_instance.get_awareness():
#                                print('---', callsign, jag_instance.get_awareness(), data)
                            # print(self.callsign + " last activity = " + str(self.last_activity_completed) + " so use awareness time " + str(jag_instance.awareness_time))
                            jag_instance.update_preparing(observer_callsign, callsign, 1.0, jag_instance.awareness_time(callsign))
                            jag_instance.update_preparing(observer_callsign, callsign, 0.0, jag_instance.awareness_time(callsign))
                        else:
                            # print(self.callsign + " last activity = " + str(self.last_activity_completed.urn) + " so use last activity time " + str(self.last_activity_completion_time))
                            jag_instance.update_preparing(observer_player_id, callsign, 1.0, player.last_activity_completion_time)
                            jag_instance.update_preparing(observer_player_id, callsign, 0.0, player.last_activity_completion_time)
                    # update addressing
                    jag_instance.update_addressing(observer_callsign, callsign, addressing[preparing_player_id], elapsed_ms)

            elif message['sub_type'] == 'Event:Completion':
                # update individual
                observer_player_id = data['participant_id']
                player = self.players[observer_player_id]
                instance_update = data['jag']
                uid = instance_update['id']
                jag_instance = player.joint_activity_model.get_by_id(uid)
                
                ########################################
                ######### USC addition
                ########################################
                if jag_instance is None: 
                    self.orphan_msgs.append([uid, message, data])
                    return
                
                completion_status = instance_update['is_complete']
                elapsed_ms = instance_update['elapsed_milliseconds']
                self.elapsed_milliseconds = elapsed_ms
                # print(jag_instance.short_string() + " completion_status " + str(completion_status) + ": " + str(elapsed_ms))
                observer_callsign = self.players[observer_player_id].callsign.lower()
                jag_instance.update_completion_status(observer_callsign, completion_status, elapsed_ms)

                # update last activity to track prepare time
                if jag_instance.urn != aj.SEARCH_AREA['urn'] and jag_instance.urn != aj.GET_IN_RANGE['urn']:
                    player.set_last_activity_completed(jag_instance)
                    player.set_last_activity_completion_time(elapsed_ms)
                
            ########################################
            ######### USC addition
            ########################################
            elif message['sub_type'] == 'Event:Summary':
#                print('Summary')
                player2jag = data['jag']['instances']
                self.compute_measure(player2jag)
#                self.print_asi_jam()
#                self.player_stats()
                
        except Exception:
            print(traceback.format_exc())
        return []
    
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


    ########################################
    ######### End of IHMC code copied from src/agents/joint_activity_client.py
    ########################################            
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
#            for l in unawareness:
#                print(l.short_string())
    
    ########################################
    ########################################
    ######### Start of IHMC code copied from src/agents/joint_activity_monitor.pyicated as such
    ########################################
    ########################################

    def compute_measure(self, player2jag):
        new_asi_jag = None
        for player_id, jag_id in player2jag.items():
            player = self.players[player_id]
            player_victim_jag = player.joint_activity_model.get_by_id(jag_id)
            if new_asi_jag is None:
                new_asi_jag = player_victim_jag
            else:
                new_asi_jag = merge_jags(new_asi_jag, player_victim_jag)

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

    ########################################
    ######### End of IHMC code copied from src/agents/joint_activity_monitor.pyicated as such
    ########################################


    def simple_stats(self):
        from collections import  Counter
        print('count of discovery message across all players by jag type\n', Counter([j.urn for j in self.debug_discover]))
        for player_id, player in self.players.items():
            player_jags = player.joint_activity_model.jag_instances
            print('jag types for player', player_id, Counter([j.urn for j in player_jags]))
            
    def debug_orphans(self):
        for uid, msg, data in self.orphan_msgs:
             mtype = msg['sub_type']
             player_id = data['participant_id']
             player = self.players[player_id]
             jag = player.joint_activity_model.get_by_id(uid)
             print(mtype, player_id, (jag is None))


def add_joint_activity(world, player, jag):
    urn = jag.urn.split(':')
    if len(jag.inputs) == 1:
        obj = next(iter(jag.inputs.values()))
    else:
        raise NameError(f'{urn} {jag.inputs}')
    feature = f'{urn[-1]}_{obj}'
    # Create status variable for this joint activity
    var = world.defineState(player.callsign, feature, list, 
                            ['discovered', 'aware', 'preparing', 'addressing', 
                             'complete'])
    world.setFeature(var, 'discovered')
    # Add reward component for progressing through this activity
    for model in world.get_current_models()[player.callsign]:
        goal = maximizeFeature(var, player.callsign)
        world.agents[player.callsign].setReward(goal, 1, model)
    # Add action for addressing this activity
    action_dict = {'verb': 'advance', 'object': obj}
    if not world.agents[player.callsign].hasAction(action_dict):
        tree = makeTree({'if': equalRow(var, 'complete'), 
                        True: False, False: True})
        world.agents[player.callsign].addAction(action_dict, tree)
        tree = makeTree({'if': equalRow(var, ['discovered', 'aware', 'preparing', 'addressing']),
                         'discovered': setToConstantMatrix(var, 'aware'),
                         'aware': setToConstantMatrix(var, 'preparing'),
                         'preparing': setToConstantMatrix(var, 'addressing'),
                         'addressing': setToConstantMatrix(var, 'complete'),
                         })
    for child in jag.children:
        add_joint_activity(world, player, child)
