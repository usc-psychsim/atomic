#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon May 25 14:33:33 2020

@author: atomic
"""
from helpers import anding
from multivic import Victims
from psychsim.pwl import makeTree, incrementMatrix, \
    equalRow, setToConstantMatrix, stateKey, noChangeMatrix, thresholdRow, addFeatureMatrix
from psychsim.world import WORLD

# mission phases
PHASE_FEATURE = 'phase'
END_STR = 'end'
NEAR_END_STR = 'near_end'
MIDDLE_STR = 'middle'
NEAR_MIDDLE_STR = 'near_middle'
START_STR = 'start'
MISSION_PHASES = [START_STR, NEAR_MIDDLE_STR, MIDDLE_STR, NEAR_END_STR, END_STR]
MISSION_PHASE_END_TIMES = [150, 300, 420, 540]

def incrementTime(world):
    clock = stateKey(WORLD,'seconds')
    world.setDynamics(clock, True, makeTree(incrementMatrix(clock, 1)))

    # updates mission phase
    phase = stateKey(WORLD, PHASE_FEATURE)
    tree = {'if': thresholdRow(clock, MISSION_PHASE_END_TIMES),
            len(MISSION_PHASE_END_TIMES): setToConstantMatrix(phase, MISSION_PHASES[-1])}
    for i, phase_time in enumerate(MISSION_PHASE_END_TIMES):
        tree[i] = setToConstantMatrix(phase, MISSION_PHASES[i])
    world.setDynamics(phase, True, makeTree(tree))


def makeExpiryDynamics(humanNames, locationNames, world, color_expiry):
    clock = stateKey(WORLD, 'seconds')

    # set every player's FOV to RED if they are seeing a victim
    vic_colors = Victims.COLORS[:-2]
    for human in humanNames:
        fovKey = stateKey(human, Victims.STR_FOV_VAR)
        deathTree = {'if': equalRow(fovKey, vic_colors),
                     None: noChangeMatrix(fovKey)}
        for i, color in enumerate(vic_colors):
            expire = color_expiry[color]
            deathTree[i] = {'if': thresholdRow(clock, expire),
                            True: setToConstantMatrix(fovKey, 'Red'),
                            False: noChangeMatrix(fovKey)}
        world.setDynamics(fovKey, True, makeTree(deathTree))

    # update victim loc counters
    for loc in locationNames:
        red_ctr = stateKey(WORLD, 'ctr_' + loc + '_' + 'Red')
        for color in vic_colors:
            ctr = stateKey(WORLD, 'ctr_' + loc + '_' + color)
            expire = color_expiry[color]

            # RED: if death time is reached, copy amount of alive victims to counter
            deathTree = {'if': thresholdRow(clock, expire),
                         True: addFeatureMatrix(red_ctr, ctr),
                         False: noChangeMatrix(red_ctr)}
            world.setDynamics(red_ctr, True, makeTree(deathTree))

            # GREEN and GOLD: if death time reached, zero-out alive victims of that color
            deathTree = {'if': thresholdRow(clock, expire),
                         True: setToConstantMatrix(ctr, 0),
                         False: noChangeMatrix(ctr)}
            world.setDynamics(ctr, True, makeTree(deathTree))


# def makeExpiryDynamics(victimsByLocAndColor, world, COLOR_EXPIRY):
#     clock = stateKey(WORLD,'seconds')
#     for colorsToVics in victimsByLocAndColor.values():
#         for color, victims in colorsToVics.items():
#             expire = COLOR_EXPIRY[color]
#             for victim in victims:
#                 clrKey = stateKey(victim.name, 'color')
#                 deathTree = anding([equalRow(clrKey, color),
#                                     thresholdRow(clock, expire)],
#                                     setToConstantMatrix(clrKey, 'Red'), noChangeMatrix(clrKey))
#                 world.setDynamics(clrKey, True, makeTree(deathTree))
        
def stochasticTriageDur(victimsObj, triageDurationDistr, world, color):
    clock = stateKey(WORLD,'seconds')
    stochTree = {'distribution': [(incrementMatrix(clock, c), p) for c,p in triageDurationDistr.items()]}
    for actions in victimsObj.triageActs.values():
        triageActColor = actions[color]
        world.setDynamics(clock, triageActColor, makeTree(stochTree))
    
        