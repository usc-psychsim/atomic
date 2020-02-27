# -*- coding: utf-8 -*-
"""
Created on Thu Feb 20 11:23:22 2020

@author: mostafh
"""

from psychsim.pwl import makeTree, setToConstantMatrix, incrementMatrix, setToFeatureMatrix, \
    equalRow, equalFeatureRow, andRow, stateKey, rewardKey, actionKey

class Victims:
    ## One entry per victim
    VICTIMS_LOCS = [5,2]
    VICTIM_TYPES = [0,1]
    numVictims = len(VICTIM_TYPES)
    
    ## Reward per victim type
    TYPE_REWARDS = [10, 200, 30]
    # number of triage actions needed to restore victim to health
    TYPE_REQD_TIMES = [1, 1, 5]     

    victimAgents = []
    triageActions = {}    
    world = None
    
    def makeVictims(humanNames):
        for vi in range(Victims.numVictims):
            victim = Victims.world.addAgent('victim' + str(vi))
            
            Victims.world.defineState(victim.name,'status',list,['unsaved','saved','dead'])
            victim.setState('status','unsaved')
        
            Victims.world.defineState(victim.name,'danger',float,description='How far victim is from health')
            victim.setState('danger', Victims.TYPE_REQD_TIMES[Victims.VICTIM_TYPES[vi]])
        
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
        Action effects: a) if danger is down to 0: 1) victim is saved, 2) victim remembers savior's name       
        b) Always decrement victim's danger
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
                        
            statusKey = stateKey(victim.name,'status')
            dangerKey = stateKey(victim.name,'danger')
            
            ## Status: if danger is down to 0, victim is saved
            tree = makeTree({'if': equalRow(dangerKey, 1),
                             True: setToConstantMatrix(statusKey, 'saved'),
                             False: setToConstantMatrix(statusKey, 'unsaved')})
            Victims.world.setDynamics(statusKey,action,tree)
                        
            ## Savior name: if danger is down to 0, set to human's name. Else none
            saviorKey = stateKey(victim.name,'savior')
            tree = makeTree({'if': equalRow(dangerKey, 1),
                             True: setToConstantMatrix(saviorKey, human.name),
                             False:setToConstantMatrix(saviorKey, 'none')})
            Victims.world.setDynamics(saviorKey,action,tree)  
                        
            ## Danger: dencrement danger by 1
            tree = makeTree(incrementMatrix(dangerKey,-1))
            Victims.world.setDynamics(dangerKey,action,tree)

    def makeVictimReward(human):
        """
        Human gets reward if: a) victim is saved; b) human is the savior; 
        c) last human action was to save this victim (so reward only obtained once)
        
        """        
        for victim in Victims.victimAgents:
            goal = makeTree({'if': equalRow(stateKey(victim.name,'status'),'saved'),
                            True: {'if': equalRow(stateKey(victim.name, 'savior'), human.name),
                                   True: setToFeatureMatrix(rewardKey(human.name),stateKey(victim.name,'reward')),
                                   False: setToConstantMatrix(rewardKey(human.name),0)},
                            False: setToConstantMatrix(rewardKey(human.name),0)})
            human.setReward(goal,1)
            
    
    
    def triage(human, victimID):
        Victims.world.step(Victims.triageActions[human.name][victimID])