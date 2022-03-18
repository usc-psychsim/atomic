#!/usr/bin/env python3

"""
utilities

author: Micael Vignati
email: mvignati@ihmc.org
"""

__author__ = 'mvignati'

import numpy as np


def xzy_location_from_dict(d: dict) -> np.ndarray:
    # avoids creation of temporary array
    location = np.ndarray((3,))
    location[0] = d['x']
    location[1] = d['z']
    location[2] = d['y']
    return location

