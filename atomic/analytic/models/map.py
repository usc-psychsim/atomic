#!/usr/bin/env python3

"""
Locally controlled client

author: Micael Vignati
email: mvignati@ihmc.org
"""

__author__ = 'mvignati'

import json

import math
import numpy as np

from ..utils.utils import xzy_location_from_dict

# walks need to be consistent with arc dividing when casting shadows
# arc start should be the smallest angle
SQUARE_TOPOLOGY = {
    'offset': np.array([1, 1], dtype=np.int16),
    'walk': np.array([[-1, 0], [0, -1], [1, 0], [0, 1]], dtype=np.int16),
    'count': 2
}

FLAT_DIAMOND_TOPOLOGY = {
    'offset': np.array([1, 1], dtype=np.int16),
    'walk': np.array([[-1, 1], [-2, 0], [-1, -1], [1, -1], [2, 0], [1, 1]], dtype=np.int16),
    'count': 1
}

DIAMOND_TOPOLOGY = {
    'offset': np.array([1, 0], dtype=np.int16),
    'walk': np.array([[-1, 1], [-1, -1], [1, -1], [1, 1]], np.int16),
    'count': 1
}

TRANSPARENT_BLOCKS = (
    'wall_sign',
    'glass_pane',
    'glass',
)

BLOCK_MAPPING = {
    'block_victim_1': 2,
    'victim_saved_a': 2,
    'block_victim_1b': 3,
    'victim_saved_b': 3,
    'block_victim_proximity': 4,
    'victim_saved_c': 4,
    'gravel': 5
}

POINTS_OF_INTEREST = [2, 3, 4]

HALF_PI = math.pi / 2


def handle_poi_detection(poi, player):
    pass


class Map:
    def __init__(self, _handle_poi_detection=handle_poi_detection):
        self.__origin = None
        self.__dimensions = None
        self.__blocks = None
        self.__points_of_interest = {}
        self.__handle_poi_detection = _handle_poi_detection

        # Temporary solution to ground truth updates
        # Map update should only notify of what's changed (map view currently rebuilds the map)
        self.__ready = 0

    @staticmethod
    def __get_ring(player, center, distance):
        ring_offsets = player.ring_offsets(distance)
        ring = ring_offsets + center
        return ring

    @staticmethod
    def __block_shadow(block):
        """
        Takes in a block location in the reference frame of the light's origin
        :param block:
        :return: start and end arc cast by the block
        """
        xs = math.copysign(.5, block[0])
        ys = math.copysign(.5, block[1])
        center_block = block

        if block[0] == 0:
            return center_block + np.array([ys, -ys]), center_block + np.array([-ys, -ys])
        elif block[1] == 0:
            return center_block + np.array([-xs, -xs]), center_block + np.array([-xs, xs])
        else:
            return center_block + np.array([ys, -xs]), center_block + np.array([-ys, xs])

    @staticmethod
    def __in_arc(start, end, v):
        start_cross = start[0] * v[1] - start[1] * v[0]
        if start_cross < 0:
            return False
        end_cross = end[0] * v[1] - end[1] * v[0]
        if end_cross > 0:
            return False
        return True

    @staticmethod
    def __in_field_of_view(arcs, block):
        for i in range(0, len(arcs) - 1, 2):
            if Map.__in_arc(arcs[i], arcs[i + 1], block):
                return i
        return None

    def __block_key(self, x, y):
        return y * self.__dimensions[0] + x

    def __local_coordinates(self, locatable):
        x = np.uint16(locatable['x'] - self.__origin[0])
        y = np.uint16(locatable['y'] - self.__origin[2])
        z = np.uint8(locatable['z'] - self.__origin[1])
        return x, y, z

    def __in_bounds(self, block):
        return 0 <= block[0] < self.__dimensions[0] and 0 <= block[1] < self.__dimensions[1]

    def __block_type(self, x, y, z):
        # uses try block instead of checking for bounds to keep performance up
        try:
            return self.__blocks[x, y, z]
        except IndexError:
            # return wall if out of bounds
            return 1

    def __cast_shadow(self, player, arcs, center, local_block):
        arc_idx = self.__in_field_of_view(arcs, local_block)
        if arc_idx is None:
            return False

        x, y = local_block + center
        feet_block_type = self.__block_type(x, y, 2)
        eye_block_type = self.__block_type(x, y, 3)

        if feet_block_type in POINTS_OF_INTEREST:
            block_key = self.__block_key(x, y)
            # if the block is a point of interest and has not been seen before by this player
            if block_key in self.__points_of_interest and block_key not in player.points_of_interest:
                poi = self.__points_of_interest[block_key]
                player.points_of_interest[block_key] = poi
                self.__handle_poi_detection(poi, player)

        if eye_block_type != 0:
            start, end = self.__block_shadow(local_block)

            arc_start = arcs[arc_idx]
            arc_end = arcs[arc_idx + 1]

            player.arcs.insert(arc_idx + 1, start)
            player.arcs.insert(arc_idx + 2, end)

            # starts with the end to keep the index meaning
            # if not self.__in_arc(arc_start, arc_end, end):
            if not self.__in_arc(arc_start, arc_end, end) or np.allclose(arc_end, end, rtol=0.98):
                arcs.pop(arc_idx + 1)
            else:
                arcs.insert(arc_idx + 1, end)

            if not self.__in_arc(arc_start, arc_end, start) or np.allclose(arc_start, start, rtol=0.98):
                arcs.pop(arc_idx)
            else:
                arcs.insert(arc_idx + 1, start)

        return True

    def on_map_update(self):
        pass

    def update_map(self, blocks):
        for block in blocks:
            x, y, z = self.__local_coordinates(block)
            block_type = BLOCK_MAPPING[block['block_type']]
            self.__blocks[x, z, y] = block_type

            # register as point of interest using its index key
            if block_type in POINTS_OF_INTEREST:
                block_key = self.__block_key(x, z)
                # @todo: this only works for victims and needs update to account for blockages
                poi_id = block['unique_id']
                self.__points_of_interest[block_key] = [x, z, block_type, poi_id]

        # only triggers map update on
        self.__ready += 1
        if self.__ready == 2:
            self.on_map_update()

    def load_map_data(self, map_name):
        with open(f'./maps/{map_name}.json', 'r') as map_file:
            map_data = json.load(map_file)

        self.__origin = xzy_location_from_dict(map_data['metadata']['lower_bound'])
        upper_bound = xzy_location_from_dict(map_data['metadata']['upper_bound'])

        self.__dimensions = (upper_bound - self.__origin) + 1

        shape = np.uint(self.__dimensions)
        self.__blocks = np.zeros(shape, dtype=np.uint8)  # zero is for air block
        for block in map_data['blocks']:
            if block['type'] in TRANSPARENT_BLOCKS:
                continue

            loc = block['location']
            x, y, z = self.__local_coordinates(loc)
            self.__blocks[x, z, y] = 1

        self.on_map_update()

    def compute_fov(self, player):
        player.arcs.clear()
        # uncomment to only record what is currently seen
        # player.points_of_interest.clear()
        arcs = [
            player.fov_bounds[0],
            player.fov_bounds[1],
        ]
        player.arcs.extend(arcs)

        np.add(player.ring_offsets, player.location, out=player.fov)
        for idx, block in enumerate(player.ring_offsets):
            player.fov_mask[idx] = self.__cast_shadow(player, arcs, player.location, block)
            if len(arcs) == 0:
                player.fov_length = idx + 1
                # break

    def remove_block(self, x, y, z):
        self.__blocks[x, y, z] = 0
        block_key = self.__block_key(x, y)
        if block_key not in self.__points_of_interest:
            return

        self.__points_of_interest.pop(block_key)
        self.on_map_update()

    def set_block(self, x, y, z, block_type, block_id):
        if block_type not in BLOCK_MAPPING:
            return

        block_type = BLOCK_MAPPING[block_type]
        self.__blocks[x, y, z] = block_type

        block_key = self.__block_key(x, y)
        self.__points_of_interest[block_key] = [x, y, block_type, block_id]

        self.on_map_update()

    @property
    def origin(self):
        return self.__origin

    @property
    def dimensions(self):
        return self.__dimensions

    @property
    def blocks(self) -> np.ndarray:
        return self.__blocks
