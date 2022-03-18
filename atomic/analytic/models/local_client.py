#!/usr/bin/env python3

"""
Locally controlled client

author: Micael Vignati
email: mvignati@ihmc.org
"""

__author__ = 'mvignati'

import math

from src.models.map import Map
from src.models.player import Player


class LocalClient:

    def __init__(self):
        self.__players = {
            'green': Player({'callsign': 'green', 'participant_id': 'P000389'})
        }
        self.__map = Map()

    def handle_mouse_motion(self, x, y):
        player = self.__players['green']
        player.x = x
        player.y = y
        self.__map.compute_fov(player)

    def handle_turn(self, direction):
        player = self.__players['green']
        player.yaw += direction * math.pi / 8
        self.__map.compute_fov(player)

    @property
    def map(self):
        return self.__map

    @property
    def players(self):
        return self.__players

    def stop(self):
        pass
