#!/usr/bin/env python3

"""
Locally controlled client

author: Micael Vignati
email: mvignati@ihmc.org
"""

__author__ = 'mvignati'


class Block:

    def __init__(self, location, block_type):
        self.__type = block_type
        self.__location = location

    @property
    def x(self):
        return self.__location[0]

    @property
    def y(self):
        return self.__location[2]

    @property
    def z(self):
        return self.__location[1]
