# -*- coding: utf-8 -*-
"""
Created on Thu Feb 20 11:23:22 2020

@author: mostafh
"""

from psychsim.pwl import makeTree, setToConstantMatrix, equalRow, equalFeatureRow, andRow, stateKey, rewardKey, actionKey

class Victims:
    ## One entry per victim
    VICTIMS_LOCS = [2]
    VICTIM_TYPES = [2]
    numVictims = len(VICTIM_TYPES)
    ## One entry per victim type
    TYPE_REWARDS = [10, 20, 30]

    victimAgents = []
    triageActions = {}    
    world = None
    
    def makeVictims(humanNames):
        for vi in range(Victims.numVictims):
            victim = Victims.world.addAgent('victim' + str(vi))
            
            Victims.world.defineState(victim.name,'status',list,['unsaved','saved','dead'])
            victim.setState('status','unsaved')
        
            Victims.world.defineState(victim.name,'health',float,description='How far away this victim is from dying')
            victim.setState('health',1)
        
            Victims.world.defineState(victim.name,'reward',int,description='Value earned by saving this victim')
            victim.setState('reward', Victims.TYPE_REWARDS[Victims.VICTIM_TYPES[vi]])
        
            Victims.world.defineState(victim.name,'loc',int,description='Room number where victim is')
            victim.setState('loc', Victims.VICTIMS_LOCS[vi])
            
            Victims.world.defineState(victim.name,'savior',list, ['none'] + humanNames, description='Name of agent who saved me, if any')
            victim.setState('savior', 'none')
            
            Victims.victimAgents.append(victim)

    def makeTriageAction(human):
        """
        Create a triage action per victim
        Legal action if: 1) human and victim are in same location; 2)victim is unsaved
        Action effects: 1) victim is saved, 2) victim remembers savior's name       
        """        
        Victims.triageActions[human.name] = []
        for victim in Victims.victimAgents:
            legalityTree = makeTree({'if': equalFeatureRow(
                                                stateKey(victim.name, 'loc'), 
                                                stateKey(human.name, 'loc')),        
                                True: {'if': equalRow(stateKey(victim.name, 'status'), 'unsaved'),
                                       True: True,
                                       False: False},
                                False: False})
            action = human.addAction({'verb': 'triage', 'object':victim.name}, legalityTree)
            Victims.triageActions[human.name].append(action)
                        
            key = stateKey(victim.name,'status')
            tree = makeTree(setToConstantMatrix(key, 'saved'))
            Victims.world.setDynamics(key,action,tree)

            key = stateKey(victim.name,'savior')
            tree = makeTree(setToConstantMatrix(key, human.name))
            Victims.world.setDynamics(key,action,tree)  

    def makeVictimReward(human):
        """
        Human doesn't know about victims a priori
        
        """
        pass
    
    
    def triage(human, victimID):
        Victims.world.step(Victims.triageActions[human.name][victimID])