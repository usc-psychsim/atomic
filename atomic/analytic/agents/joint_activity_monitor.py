#!/usr/bin/env python3

"""
IHMC Interdependence Analytic Component

author: Micael Vignati
email: mvignati@ihmc.org
"""

__author__ = 'mvignati'

import logging
import traceback

import itertools
import math
from asistagenthelper import ASISTAgentHelper

from ..models.events import JagEvent
from ..models.jags import asist_jags as aj
from ..models.jags.jag import Jag
from ..models.map import Map
from ..models.player import Player
from ..utils.jag_utils import merge_jags

TO_RADIANS = math.pi / 180

PLAYER_SPEED = {}

JAG_EVENT_TOPIC = 'observations/events/player/jag'
JAG_EVENT_VERSION = "1.2.8"
JAG_EVENT_TYPE = 'event'
JAG_EVENT_SUB_TYPES = {
    JagEvent.DISCOVERED: 'Event:Discovered',
    JagEvent.AWARENESS: 'Event:Awareness',
    JagEvent.PREPARING: 'Event:Preparing',
    JagEvent.ADDRESSING: 'Event:Addressing',
    JagEvent.COMPLETION: 'Event:Completion',
    JagEvent.SUMMARY: 'Event:Summary',
}


class JointActivityMonitor(ASISTAgentHelper):

    def __init__(self):
        super().__init__(self.__on_message_handler)
        self.__logger = logging.getLogger(__name__)
        self.__players: dict[str, Player] = {}
        self.__map = Map(self.__handle_poi_detection)
        self.__transitions = {}

        self.__topic_handlers = {
            'trial': self.__handle_trial,
            'observations/state': self.__handle_state,
            'ground_truth/mission/victims_list': self.__handle_victim_list,
            'ground_truth/mission/blockages_list': self.__handle_blockages_list,
            'ground_truth/semantic_map/initialized': self.__handle_semantic_map,
            'observations/events/player/triage': self.__handle_triage,
            'observations/events/player/victim_picked_up': self.__handle_victim_picked_up,
            'observations/events/player/victim_placed': self.__handle_victim_placed,
            'observations/events/player/location': self.__handle_location_change,
            'observations/events/player/proximity_block': self.__handle_proximity_block,
            'observations/events/player/proximity': self.__handle_proximity
        }

    @property
    def map(self):
        return self.__map

    @property
    def players(self):
        return self.__players

    def handle_mouse_motion(self, x, y):
        pass

    def handle_turn(self, direction):
        pass

    def stop(self):
        self.stop_agent_loop_thread()

    def start(self):
        self.set_agent_status(ASISTAgentHelper.STATUS_UP)
        self.start_agent_loop_thread()

    def __on_message_handler(self, topic, header, message, data, mqtt_message):
        try:
            if 'victim_id' in data:
                if data['victim_id'] == 66 or data['victim_id'] == 66:
                    print(f"{topic}\n\t{message}\n\t{data}")
            # handle specific first
            if topic in self.__topic_handlers:
                self.__topic_handlers[topic](header, message, data)
            # then dispatch to jag instances
            if self.__players is not None:
                if 'participant_id' in data:
                    player_id = data['participant_id']
                    player = self.__players[player_id]
                    event_type = message["sub_type"]
                    player.joint_activity_model.dispatch(event_type, data)
        except Exception as error:
            error_string = f"\n" \
                           f"error: {str(error)}\n" \
                           f"\tmqtt:\n" \
                           f"\t\ttopic: {topic}\n" \
                           f"\t\theader: {header}\n" \
                           f"\t\tmessage: {message}\n" \
                           f"\t\tdata: {data}\n" \
                           f"\ttraceback: {traceback.format_exc()}"
            self.__logger.error(error_string)

    def __handle_trial(self, header, message, data):
        map_name = f"{data['map_name']}-fov_map"
        self.__map.load_map_data(map_name)
        self.__players = {}
        for client in data['client_info']:
            self.__players[client['participant_id']] = Player(client)

    def __handle_victim_list(self, header, message, data):
        victim_list = data['mission_victim_list']
        self.__map.update_map(victim_list)

    def __handle_blockages_list(self, header, message, data):
        blockages_list = data['mission_blockage_list']
        self.__map.update_map(blockages_list)

    def __handle_semantic_map(self, header, message, data):
        semantic_map = data['semantic_map']
        for connection in semantic_map['connections']:
            locations = connection['connected_locations']
            simple_locations = set(map(lambda l: l.rsplit(sep='_', maxsplit=1)[0], locations))
            for source, destination in itertools.permutations(simple_locations, 2):
                if source not in self.__transitions:
                    self.__transitions[source] = set()

                destinations = self.__transitions[source]
                destinations.add(destination)

    def __handle_victim_picked_up(self, header, message, data):
        x = int(data['victim_x'] - self.__map.origin[0])
        y = int(data['victim_z'] - self.__map.origin[1])
        z = int(data['victim_y'] - self.__map.origin[2])
        self.__map.remove_block(x, y, z)
        # instantiate if needed
        victim_id = data['victim_id']
        victim_type = self.__convert_victim_type(data['type'])
        player_id = data['participant_id']
        player = self.__players[player_id]
        elapsed_ms = data['elapsed_milliseconds']
        if self.__is_player_unaware(victim_id, victim_type, player):
            self.get_logger().debug(f"__handle_victim_picked_up: no joint activity instance found, created a new one for {player.callsign} victim {victim_id} {victim_type}")
            self.__instantiate_on_discovery(victim_id, victim_type, player, elapsed_ms)
        else:
            self.get_logger().debug(f"__handle_victim_picked_up: joint activity instance already exists for {player.callsign} victim {victim_id} {victim_type}")

    def __handle_victim_placed(self, header, message, data):
        x = int(data['victim_x'] - self.__map.origin[0])
        y = int(data['victim_z'] - self.__map.origin[1])
        z = int(data['victim_y'] - self.__map.origin[2])
        self.__map.set_block(x, y, z, data['type'], data['victim_id'])

    def __handle_state(self, header, message, data):
        self.__em = data['elapsed_milliseconds']
        player_id = data['participant_id']
        player = self.__players[player_id]
        player.x = data['x'] - self.__map.origin[0]
        player.y = data['z'] - self.__map.origin[1]
        player.yaw = data['yaw'] * TO_RADIANS

        self.__map.compute_fov(player)

    def __handle_location_change(self, header, message, data):
        if 'locations' not in data:
            return

        em = data['elapsed_milliseconds']
        if em == -1:
            return

        player_id = data['participant_id']
        for location in data['locations']:
            location_id = location['id']
            semantic_location_id = location_id.rsplit(sep='_', maxsplit=1)[0]
            if semantic_location_id in self.__transitions:
                for connected_location_id in self.__transitions[semantic_location_id]:
                    self.__generate_sub_exploration_instance(connected_location_id, player_id, em)

    def __handle_poi_detection(self, poi, player):
        # @todo: find a better way to associate current time
        #  (it should probably match the state event that generated the seen event)
        elapsed_ms = self.__em
        x, y, poi_type, poi_id = poi
        self.get_logger().debug(
            f"Point of interest detected: type={poi_type}, id={poi_id}, player={player.id} {player.callsign}")
        # @todo: updates replace poi numeric type (map storage) by its enum
        victim_type = 'critical'
        if poi_type == 2:
            victim_type = 'a'
        elif poi_type == 3:
            victim_type = 'b'
        if self.__is_player_unaware(poi_id, victim_type, player):
            self.get_logger().debug(f"__handle_poi_detection: no joint activity instance found, created a new one for {player.callsign} victim {poi_id} {victim_type}")
            self.__instantiate_on_discovery(poi_id, victim_type, player, elapsed_ms)
        else:
            self.get_logger().debug(f"__handle_poi_detection: joint activity instance already exists for {player.callsign} victim {poi_id} {victim_type}")

    def __is_player_unaware(self, victim_id, victim_type, player):
        jag = aj.RESCUE_VICTIM
        urn = jag['urn']
        inputs = {'victim-id': victim_id, 'victim-type': victim_type}
        instance = player.joint_activity_model.get(urn, inputs)
        return instance is None

    def __instantiate_on_discovery(self, victim_id, victim_type, player, elapsed_ms):
        jag = aj.RESCUE_VICTIM
        urn = jag['urn']
        inputs = {'victim-id': victim_id, 'victim-type': victim_type}
        instance = player.joint_activity_model.create(urn, inputs)
        self.publish_discovery(player.id, instance)

        instance.add_observer(self.notify)
        instance.update_awareness(player.id, player.id, 1.0, elapsed_ms)

        if instance.urn == aj.RESCUE_VICTIM['urn']:
            instance.add_observer(player.notify)
            stabilize_jag = instance.get_by_urn(aj.STABILIZE['urn'], instance.inputs)
            stabilize_jag.set_estimated_addressing_duration(2.7)

        if victim_type == 'a' or victim_type == 'b':
            jag = aj.CHECK_IF_UNLOCKED
            check_if_unlocked_urn = jag['urn']
            check_if_unlocked = instance.get_by_urn(check_if_unlocked_urn, inputs)
            check_if_unlocked.update_addressing(player.id, player.id, 1.0, elapsed_ms)
            check_if_unlocked.update_addressing(player.id, player.id, 0.0, elapsed_ms)
            check_if_unlocked.update_completion_status(player.id, True, elapsed_ms)

    def __handle_triage(self, header, message, data):
        # instantiate if needed
        victim_id = data['victim_id']
        victim_type = self.__convert_victim_type(data['type'])
        player_id = data['participant_id']
        player = self.__players[player_id]
        elapsed_ms = data['elapsed_milliseconds']
        if self.__is_player_unaware(victim_id, victim_type, player):
            self.get_logger().debug(f"__handle_triage: no joint activity instance found, created a new one for {player.callsign} victim {victim_id} {victim_type}")
            self.__instantiate_on_discovery(victim_id, victim_type, player, elapsed_ms)
        else:
            self.get_logger().debug(f"__handle_triage: joint activity instance already exists for {player.callsign} victim {victim_id} {victim_type}")

    def __convert_victim_type(self, victim_type):
        if victim_type == 'victim_a' or victim_type == 'victim_saved_a':
            victim_type = 'a'
        elif victim_type == 'victim_b' or victim_type == 'victim_saved_b':
            victim_type = 'b'
        else:
            victim_type = 'critical'

        return victim_type

    def __generate_sub_exploration_instance(self, location_id, player_id, elapsed_millisecond):
        jag = aj.SEARCH_AREA
        urn = jag['urn']
        inputs = {'area': location_id}
        player = self.__players[player_id]
        instance = player.joint_activity_model.get(urn, inputs)
        if instance is None:
            instance = player.joint_activity_model.create(urn, inputs)
            instance.add_observer(self.notify)
            self.publish_discovery(player.id, instance)
            if elapsed_millisecond < 0.0:
                elapsed_millisecond = 0.0
            instance.update_awareness(player.id, player.id, 1.0, elapsed_millisecond)

    def __handle_proximity_block(self, header, message, data):
        poi_id = data['victim_id']
        elapsed_ms = data['elapsed_milliseconds']
        player_id = data['participant_id']
        player = self.__players[player_id]
        # self.get_logger().info(f"poi seen through proximity type=critical, id={poi_id}, player={player.id} {player.callsign}")
        # @todo: updates replace poi numeric type (map storage) by its enum
        jag = aj.RESCUE_VICTIM
        urn = jag['urn']
        victim_type = 'critical'
        inputs = {'victim-id': poi_id, 'victim-type': victim_type}
        instance = player.joint_activity_model.get(urn, inputs)
        if instance is None:
            instance = player.joint_activity_model.create(urn, inputs)
            instance.add_observer(self.notify)
            if instance.urn == aj.RESCUE_VICTIM['urn']:
                instance.add_observer(player.notify)
                stabilize_jag = instance.get_by_urn(aj.STABILIZE['urn'], instance.inputs)
                stabilize_jag.set_estimated_addressing_duration(3.0)
            self.publish_discovery(player.id, instance)
            instance.update_awareness(player.id, player.id, 1.0, elapsed_ms)

    def __handle_proximity(self, header, message, data):
        if 'participants' not in data:
            return
        for player_proximity in data['participants']:
            player_id = player_proximity['participant_id']
            if player_id not in self.__players:
                continue
            player = self.__players[player_id]
            player.set_proximity_info(player_proximity)

    def notify(self, observer_player_id, event_type, data, elapsed_ms):
        self.publish_update(observer_player_id, event_type, data, elapsed_ms)
        if event_type == JagEvent.COMPLETION:
            jag = data
            if jag.urn == aj.MOVE_VICTIM_TO_TRIAGE_AREA['urn']:
                relocate = jag.get_by_urn(aj.RELOCATE_VICTIM['urn'], jag.inputs, jag.outputs)
                do_children_satisfy_completion = relocate.do_children_satisfy_completion()
                if not do_children_satisfy_completion:
                    relocate.update_completion_status(observer_player_id, do_children_satisfy_completion, elapsed_ms)
                    jag.update_completion_status(observer_player_id, do_children_satisfy_completion, elapsed_ms)
                if jag.is_complete():
                    self.compute_measure(jag)

    def publish_update(self, observer_player_id, event_type, jag, elapsed_ms):
        if event_type == JagEvent.ADDRESSING:
            jag = jag['jag']
        update_data = jag.get_data(event_type, elapsed_ms)
        message_data = {
            'participant_id': observer_player_id,
            'jag': update_data
        }
        self.__publish_jag_event(event_type, message_data)

    def publish_discovery(self, observer_player_id, jag):
        instance_data = jag.get_instance_data()
        message_data = {
            'participant_id': observer_player_id,
            'jag': instance_data
        }
        self.__publish_jag_event(JagEvent.DISCOVERED, message_data)

    def __publish_jag_event(self, event_sub_type, data):
        event_sub_type_string = JAG_EVENT_SUB_TYPES[event_sub_type]
        event_string = f"\n" \
                       f"topic: {JAG_EVENT_TOPIC}\n" \
                       f"event: {JAG_EVENT_TYPE}:{event_sub_type_string}:{JAG_EVENT_VERSION}\n" \
                       f"data: {data}\n" \
                       f"traceback: {traceback.format_exc()}\n"
        self.__logger.debug(event_string)
        self.send_msg(JAG_EVENT_TOPIC, JAG_EVENT_TYPE, event_sub_type_string, JAG_EVENT_VERSION, data=data)

    def compute_measure(self, jag: Jag):
        instances: dict[str, str] = {}
        merged_jag = None
        last_player_id = None
        for player_id in self.__players:
            last_player_id = player_id
            player = self.__players[player_id]
            player_victim_jag = player.joint_activity_model.get(aj.RESCUE_VICTIM['urn'], jag.inputs, jag.outputs)
            if player_victim_jag is not None:
                instances[player_id] = player_victim_jag.id_string
                if merged_jag is None:
                    merged_jag = player_victim_jag
                else:
                    merged_jag = merge_jags(merged_jag, player_victim_jag)

        self.recheck_completion(merged_jag, last_player_id)
        estimate = merged_jag.estimated_completion_duration
        active_duration = merged_jag.completion_duration()
        non_overlapping_duration = merged_jag.completion_non_overlapping_duration()
        man_hour_efficiency = non_overlapping_duration / active_duration
        joint_activity_efficiency = estimate / active_duration
        message_data = {
            "jag": {
                "instances": instances,
                "inputs": merged_jag.inputs,
                "urn": merged_jag.urn,
            },
            "active_duration": active_duration,
            "joint_activity_efficiency": joint_activity_efficiency,
            "redundancy_ratio": 1 - man_hour_efficiency
        }
        self.__publish_jag_event(JagEvent.SUMMARY, message_data)

    # used to update completion status after merging jags
    def recheck_completion(self, jag: Jag, player_id):
        if jag.is_leaf:
            jag.update_completion_status(player_id, jag.is_complete(), jag.completion_time)
        else:
            for child in jag.children:
                self.recheck_completion(child, player_id)
