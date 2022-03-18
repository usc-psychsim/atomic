import math
import numpy as np

from .events import JagEvent
from .joint_activity_model import JointActivityModel
from .map import DIAMOND_TOPOLOGY
from ..models.jags import asist_jags as aj

PLAYER_COLORS = {
    'red': np.array((255, 0, 0)),
    'green': np.array((0, 255, 0)),
    'blue': np.array((128, 128, 255)),
}

TREATMENT_AREA_MAP = {
    'critical': ['tacn', 'tacs'],
    'a': ['taan', 'taas'],
    'b': ['tabn', 'tabs']
}

# Values computed from code in joint_activity_monitor based on real data from trial 460
TRANSPORTER_SPEED_IN_BLOCKS_PER_SEC = 4.37
MEDIC_SPEED_IN_BLOCKS_PER_SEC = 3.87
ENGINEER_SPEED_IN_BLOCKS_PER_SEC = 2.41

DEFAULT_WINDOW_DIMENSIONS = (852, 480)
DEFAULT_VERTICAL_FOV = 70 * math.pi / 180


class Player:

    def __init__(self, client_info):
        self.__client_info = client_info
        self.__role = None
        self.__horizontal_fov = Player.__get_horizontal_fov(DEFAULT_VERTICAL_FOV, DEFAULT_WINDOW_DIMENSIONS)
        self.__fov_radius = 40
        self.__fov_ring_stride_factor = 0
        self.__ring_offsets = None
        self.__fov_mask = None
        self.__fov_map = None
        self.__fov_length = 0
        self.__points_of_interest = {}
        self.__location = np.zeros((2,), dtype=np.int16)
        self.__yaw = 0
        self.__update_fov_bounds()
        self.__arcs = []
        self.__proximity_info = {}
        self.color = PLAYER_COLORS[client_info['callsign'].lower()]
        self.last_update = 0
        self.joint_activity_model = JointActivityModel(aj.ASIST_JAGS)

        self.__init_fov()

        # stuff to track what was being done previously
        self.__last_activity_completed = None
        self.__last_activity_completion_time = 0

    @staticmethod
    def __get_horizontal_fov(vertical_fov, window_dimensions):
        ratio = window_dimensions[0] / window_dimensions[1]
        return vertical_fov * ratio

    @staticmethod
    def __init_ring(d, starting_offset, count, walk, ring):
        block_count_per_side = d * count
        block = starting_offset * d

        ring_cell_idx = 0
        for direction in walk:
            for i in range(block_count_per_side):
                ring[ring_cell_idx] = block
                block = block + direction
                ring_cell_idx += 1

    def __init_fov(self):
        self.__init_ring_offsets(DIAMOND_TOPOLOGY)
        self.__fov_mask = np.ndarray((self.__ring_offsets.shape[0]), dtype=np.bool)
        self.__fov_map = np.ndarray(self.__ring_offsets.shape, dtype=np.int16)

    def __fov_ring_index_offset(self, d):
        # s=number of sides, c=block per side count factor (multiply by distance for actual block count)
        # s * c * 1 + s * c * 2 + ... + s * c * distance
        # s * c * (1 + 2 + ... + distance)
        # s * c * [distance * (distance + 1) / 2]
        return np.uint(self.__fov_ring_stride_factor * d * (d + 1) / 2)

    def __init_ring_offsets(self, topology):
        count = topology['count']
        walk = topology['walk']
        sides = len(walk)
        distance = self.__fov_radius
        self.__fov_ring_stride_factor = sides * count

        fov_size = self.__fov_ring_index_offset(distance)

        self.__ring_offsets = np.zeros((fov_size, 2), dtype=np.int8)

        for d in range(1, distance + 1):
            index_offset = self.__fov_ring_index_offset(d - 1)
            # creates a view at the correct offset to be populated by __init_ring
            ring = self.__ring_offsets[index_offset:]
            self.__init_ring(d, topology['offset'], count, walk, ring)

    def __update_fov_bounds(self):
        start_theta = self.__yaw - self.__horizontal_fov / 2
        end_theta = self.__yaw + self.__horizontal_fov / 2
        self.__fov_bounds = (
            np.array([-math.sin(start_theta), math.cos(start_theta)]),
            np.array([-math.sin(end_theta), math.cos(end_theta)])
        )

    @property
    def id(self):
        return self.__client_info['participant_id']

    @property
    def callsign(self):
        return self.__client_info['callsign']

    @property
    def x(self):
        return self.__location[0]

    @property
    def y(self):
        return self.__location[1]

    @property
    def yaw(self):
        return self.__yaw

    @property
    def horizontal_fov(self):
        return self.__horizontal_fov

    @property
    def fov_radius(self):
        return self.__fov_radius

    @property
    def points_of_interest(self):
        return self.__points_of_interest

    @x.setter
    def x(self, value):
        self.__location[0] = value

    @y.setter
    def y(self, value):
        self.__location[1] = value

    @yaw.setter
    def yaw(self, value):
        self.__yaw = value
        self.__update_fov_bounds()

    @property
    def location(self):
        return self.__location

    @property
    def fov(self):
        return self.__fov_map

    @property
    def fov_mask(self):
        return self.__fov_mask

    @property
    def fov_length(self):
        return self.__fov_length

    @fov_length.setter
    def fov_length(self, value):
        self.__fov_length = value

    @property
    def fov_bounds(self):
        return self.__fov_bounds

    @property
    def arcs(self):
        return self.__arcs

    @property
    def ring_offsets(self):
        return self.__ring_offsets

    @property
    def role(self):
        return self.__role

    def set_role(self, role):
        self.__role = role

    @property
    def proximity_info(self):
        return self.__proximity_info

    def set_proximity_info(self, proximity_info):
        self.__proximity_info = proximity_info

    @property
    def last_activity_completed(self):
        return self.__last_activity_completed

    def set_last_activity_completed(self, last_activity_completed):
        self.__last_activity_completed = last_activity_completed

    @property
    def last_activity_completion_time(self):
        return self.__last_activity_completion_time

    def set_last_activity_completion_time(self, last_activity_completion_time):
        self.__last_activity_completion_time = last_activity_completion_time

    # The listener is used to try to infer prepare time from last activity
    def notify(self, observer_player_id, event_type, data, elapsed_ms):
        if event_type == JagEvent.ADDRESSING:
            jag_instance = data['jag']
            player_id = data['addressing_player_id']
            confidence_value = data['confidence_value']
            if confidence_value > 0.0:
                if jag_instance.urn == aj.AT_PROPER_TRIAGE_AREA['urn']:
                    jag_instance.update_preparing(observer_player_id, player_id, 1.0, elapsed_ms)
                    jag_instance.update_preparing(observer_player_id, player_id, 0.0, elapsed_ms)
                else:
                    if self.last_activity_completed is None:
                        jag_instance.update_preparing(observer_player_id, player_id, 1.0,
                                                      jag_instance.awareness_time(self.id))
                        jag_instance.update_preparing(observer_player_id, player_id, 0.0, elapsed_ms)
                    else:
                        jag_instance.update_preparing(observer_player_id, player_id, 1.0, self.last_activity_completion_time)
                        jag_instance.update_preparing(observer_player_id, player_id, 0.0, elapsed_ms)
        elif event_type == JagEvent.COMPLETION:
            jag_instance = data
            if jag_instance.urn != aj.SEARCH_AREA['urn'] and jag_instance.urn != aj.GET_IN_RANGE['urn']:
                self.set_last_activity_completed(jag_instance)
                self.set_last_activity_completion_time(elapsed_ms)
                # print(self.callsign + " setting last activity = " + str(self.last_activity_completed.urn) + ": " + str(self.last_activity_completion_time))
            if jag_instance.urn == aj.DIAGNOSE['urn']:
                # do something to estimate move time
                victim_id = jag_instance.inputs['victim-id']
                victim_type = jag_instance.inputs['victim-type']
                min_dist = 999999
                if victim_type in TREATMENT_AREA_MAP and 'distance_to_treatment_areas' in self.__proximity_info:
                    for treatment_area in self.__proximity_info['distance_to_treatment_areas']:
                        if treatment_area['id'] in TREATMENT_AREA_MAP[victim_type]:
                            if treatment_area['distance'] < min_dist:
                                min_dist = treatment_area['distance']
                    if min_dist < 999999:
                        travel_time = min_dist / TRANSPORTER_SPEED_IN_BLOCKS_PER_SEC
                        # print(f'Diagnose Victim {str(victim_id)} of type: {victim_type}  transporter_travel_time_to_treatment_area = {str(travel_time)} seconds')
                        rescue_jag = self.joint_activity_model.get(aj.RESCUE_VICTIM['urn'], jag_instance.inputs)
                        drop_off_jag = rescue_jag.get_by_urn(aj.DROP_OFF_VICTIM['urn'], jag_instance.inputs)
                        drop_off_jag.set_estimated_addressing_duration(travel_time)
