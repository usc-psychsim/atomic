#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon May 25 14:33:33 2020

@author: atomic
"""
from victims_fewacts import Victims
from psychsim.world import WORLD

class FatherTime:
    def __init__(self, world, willAct=False):
        self.world = world
        self.timeInSec = 0
        self.timeKey = world.defineState(WORLD,'stime',int,description='Elapsed time in seconds')
        world.setFeature(self.timeKey, 0)
        
    def setTimeTo(self, seconds):
        self.world.setFeature(self.timeKey, seconds)
        self.timeInSec = seconds
        self.checkExpiry()

    def incrTimeBy(self, seconds):
        self.timeInSec = self.timeInSec + seconds
        self.world.setFeature(self.timeKey, self.timeInSec)
        self.checkExpiry()
        
    def tick(self):
        """
        Advance time by directly setting the feature
        """
        self.timeInSec = self.timeInSec + 1
        self.world.setFeature(self.timeKey, self.timeInSec)
        self.checkExpiry()
        
#    def tickAction(self):
#        """
#        Advance time by taking the action that advances
#        """
#        self.world.step(self.advanceAct)
#        self.timeInSec = self.timeInSec + 1
#        self.checkExpiry()
        
    def checkExpiry(self):
        for vic in Victims.victimAgents:
            if vic.expiry < self.timeInSec:
                vic.vicAgent.setState('status', 'dead')
            
        