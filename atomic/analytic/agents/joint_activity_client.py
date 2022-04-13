import logging
import json
import traceback

from asistagenthelper import ASISTAgentHelper

from ..models.joint_activity_model import JointActivityModel
from ..models.jags import asist_jags as aj
from ..models.player import Player

LOGGER = "JagVisualizerAC"
LOG_HANDLER = logging.StreamHandler()
LOG_HANDLER.setFormatter(logging.Formatter("%(asctime)s | %(name)s | %(levelname)s — %(message)s"))


class JointActivityClient(ASISTAgentHelper):

    def __init__(self):
        super().__init__(self.__on_message_handler)

        self.logger = logging.getLogger(LOGGER)
        self.logger.setLevel(logging.INFO)
        self.logger.addHandler(LOG_HANDLER)
        self.logger.info('Starting IHMC\'s JAG Visualizer Agent')

        self.__topic_handlers = {
            'trial': self.__handle_trial,
            'observations/events/player/jag': self.__handle_jag,
            'observations/events/mission': self.__handle_mission,
            'observations/events/player/role_selected': self.__handle_role
        }

        self.__players = {}
        self.__elapsed_milliseconds = 0
        self.__started = False

    def players(self):
        return self.__players

    def stop(self):
        self.stop_agent_loop_thread()

    def start(self):
        self.set_agent_status(ASISTAgentHelper.STATUS_UP)
        self.logger.info("Starting Agent Loop on a separate thread.")
        self.start_agent_loop_thread()
        self.logger.info("Agent is now running...")

    def __on_message_handler(self, topic, header, message, data, json_data):
        if topic not in self.__topic_handlers:
            return

        self.__topic_handlers[topic](header, message, data)

    def __handle_trial(self, header, message, data):
        players = {}
        for client in data['client_info']:
            players[client['participant_id']] = Player(client)
        self.__players.update(players)

    def __handle_mission(self, header, message, data):
        self.__elapsed_milliseconds = data['elapsed_milliseconds']
        state = data['mission_state']
        if state == 'Start':
            self.__started = True
        if state == 'Stop':
            self.__started = False

    def __handle_role(self, header, message, data):
        player_id = data['participant_id']
        role = data['new_role']
        player = self.__players[player_id]
        player.set_role(role)

    def __handle_jag(self, header, message, data):
        try:
            if message['sub_type'] == 'Event:Discovered':
                player_id = data['participant_id']
                player = self.__players[player_id]
                instance_description = data['jag']
                jag = player.joint_activity_model.create_from_instance(instance_description)
                # self.logger.info("discovered " + jag.short_string())
            elif message['sub_type'] == 'Event:Awareness':
                observer_player_id = data['participant_id']
                player = self.__players[observer_player_id]
                instance_update = data['jag']
                uid = instance_update['id']
                jag_instance = player.joint_activity_model.get_by_id(uid)
                awareness = instance_update['awareness']
                # self.logger.info(jag_instance.short_string() + " awareness " + str(awareness))
                elapsed_ms = instance_update['elapsed_milliseconds']
                self.__elapsed_milliseconds = elapsed_ms
                observer_callsign = self.__players[observer_player_id].callsign.lower()
                for aware_player_id in awareness.keys():
                    callsign = self.__players[aware_player_id].callsign.lower()
                    jag_instance.update_awareness(observer_callsign, callsign, awareness[aware_player_id], elapsed_ms)
            elif message['sub_type'] == 'Event:Preparing':
                # update individual
                observer_player_id = data['participant_id']
                player = self.__players[observer_player_id]
                instance_update = data['jag']
                uid = instance_update['id']
                jag_instance = player.joint_activity_model.get_by_id(uid)
                preparing = instance_update['preparing']
                # self.logger.info(jag_instance.short_string() + " preparing " + str(preparing))
                elapsed_ms = instance_update['elapsed_milliseconds']
                self.__elapsed_milliseconds = elapsed_ms
                observer_callsign = self.__players[observer_player_id].callsign.lower()
                for preparing_player_id in preparing.keys():
                    callsign = self.__players[preparing_player_id].callsign.lower()
                    # update preparing based on last activity
                    if preparing[preparing_player_id] > 0.0:
                        jag_instance.update_preparing(observer_callsign, callsign, preparing[preparing_player_id], elapsed_ms)
                        # if callsign.lower() == 'red':
                        #     self.logger.info(jag_instance.short_string() + " red preparing " + str(preparing))
                # for jag in player.joint_activity_model.jag_instances:
                #     self.logger.info(jag.to_string())
            elif message['sub_type'] == 'Event:Addressing':
                # update individual
                observer_player_id = data['participant_id']
                player = self.__players[observer_player_id]
                instance_update = data['jag']
                uid = instance_update['id']
                jag_instance = player.joint_activity_model.get_by_id(uid)
                addressing = instance_update['addressing']
                # self.logger.info(jag_instance.short_string() + " addressing " + str(addressing))
                elapsed_ms = instance_update['elapsed_milliseconds']
                self.__elapsed_milliseconds = elapsed_ms
                observer_callsign = self.__players[observer_player_id].callsign.lower()
                for preparing_player_id in addressing.keys():
                    callsign = self.__players[preparing_player_id].callsign.lower()
                    # update preparing based on last activity
                    if addressing[preparing_player_id] > 0.0:
                        if player.last_activity_completed is None:
                            # print(self.callsign + " last activity = " + str(self.last_activity_completed) + " so use awareness time " + str(jag_instance.awareness_time))
                            jag_instance.update_preparing(observer_callsign, callsign, 1.0, jag_instance.awareness_time(callsign))
                            jag_instance.update_preparing(observer_callsign, callsign, 0.0, jag_instance.awareness_time(callsign))
                        else:
                            # print(self.callsign + " last activity = " + str(self.last_activity_completed.urn) + " so use last activity time " + str(self.last_activity_completion_time))
                            jag_instance.update_preparing(observer_player_id, callsign, 1.0, player.last_activity_completion_time)
                            jag_instance.update_preparing(observer_player_id, callsign, 0.0, player.last_activity_completion_time)
                    # update addressing
                    jag_instance.update_addressing(observer_callsign, callsign, addressing[preparing_player_id], elapsed_ms)
                    # self.logger.info(jag_instance.short_string() + " addressing " + str(addressing))
                # for jag in player.joint_activity_model.jag_instances:
                    #     self.logger.info(jag.to_string())
            elif message['sub_type'] == 'Event:Completion':
                # update individual
                observer_player_id = data['participant_id']
                player = self.__players[observer_player_id]
                instance_update = data['jag']
                uid = instance_update['id']
                jag_instance = player.joint_activity_model.get_by_id(uid)
                completion_status = instance_update['is_complete']
                elapsed_ms = instance_update['elapsed_milliseconds']
                self.__elapsed_milliseconds = elapsed_ms
                # self.logger.info(jag_instance.short_string() + " completion_status " + str(completion_status) + ": " + str(elapsed_ms))
                observer_callsign = self.__players[observer_player_id].callsign.lower()
                jag_instance.update_completion_status(observer_callsign, completion_status, elapsed_ms)

                # update last activity to track prepare time
                if jag_instance.urn != aj.SEARCH_AREA['urn'] and jag_instance.urn != aj.GET_IN_RANGE['urn']:
                    player.set_last_activity_completed(jag_instance)
                    player.set_last_activity_completion_time(elapsed_ms)
        except Exception:
            print(traceback.format_exc())

    def __get_player_by_callsign(self, callsign):
        for player in self.__players.values():
            if player.callsign.lower() == callsign.lower():
                return player
        return None

    def team_summary(self):
        if self.__started:
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
            elapsed_minutes = self.__elapsed_milliseconds / 1000 / 60
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







