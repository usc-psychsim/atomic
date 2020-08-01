#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon May 25 14:33:33 2020

@author: atomic
"""
from helpers import anding

from psychsim.pwl import makeTree, setToConstantMatrix, incrementMatrix, setToFeatureMatrix, \
    equalRow, equalFeatureRow, andRow, stateKey, rewardKey, actionKey, isStateKey, state2agent, \
    Distribution, noChangeMatrix, thresholdRow
from psychsim.world import WORLD

def incrementTime(world):
    clock = stateKey(WORLD,'seconds')
    world.setDynamics(clock, True, makeTree(incrementMatrix(clock, 1)))

def makeExpiryDynamics(victimsByLocAndColor, world, COLOR_EXPIRY):
    clock = stateKey(WORLD,'seconds')
    for colorsToVics in victimsByLocAndColor.values():
        for color, victim in colorsToVics.items():
            expire = COLOR_EXPIRY[color]
            clrKey = stateKey(victim.name, 'color')
            deathTree = anding([equalRow(clrKey, color),
                                thresholdRow(clock, expire)], 
                                setToConstantMatrix(clrKey, 'Red'), noChangeMatrix(clrKey))
            world.setDynamics(clrKey, True, makeTree(deathTree))
        

        