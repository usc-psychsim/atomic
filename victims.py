# -*- coding: utf-8 -*-
"""
Created on Thu Feb 20 11:23:22 2020

@author: mostafh
"""

from psychsim.pwl import makeTree, setToConstantMatrix, incrementMatrix, setToFeatureMatrix, \
    equalRow, equalFeatureRow, andRow, stateKey, rewardKey, actionKey, isStateKey, state2agent, \
    Distribution
import locations

class Victims:
    FULL_OBS = None
    ## Reward per victim type
    TYPE_REWARDS = [10, 200, 30]
    # number of triage actions needed to restore victim to health
    TYPE_REQD_TIMES = [1, 1, 5]     

    victimAgents = []
    triageActions = {}    
    world = None
    
    def makeVictims(vLocations, vTypes, humanNames):
        assert(len(vLocations) == len(vTypes))
        Victims.numVictims = len(vTypes)
        for vi in range(Victims.numVictims):
            victim = Victims.world.addAgent('victim' + str(vi))
            
            Victims.world.defineState(victim.name,'status',list,['unsaved','saved','dead'])
            victim.setState('status','unsaved')
        
            Victims.world.defineState(victim.name,'danger',float,description='How far victim is from health')
            victim.setState('danger', Victims.TYPE_REQD_TIMES[vTypes[vi]])
        
            Victims.world.defineState(victim.name,'reward',int,description='Value earned by saving this victim')
            victim.setState('reward', Victims.TYPE_REWARDS[vTypes[vi]])
        
            Victims.world.defineState(victim.name,'loc',int,description='Room number where victim is')
            victim.setState('loc', vLocations[vi])
            
            Victims.world.defineState(victim.name,'savior',list, ['none'] + humanNames, description='Name of agent who saved me, if any')
            victim.setState('savior', 'none')
            
            Victims.victimAgents.append(victim)
    
    def makeVictimObservationVars(human):
        """
        Create observed varibles 
        """
        Victims.world.defineState(human, 'obs_victim_status', list,['null', 'unsaved','saved','dead'])
        human.setState('obs_victim_status','null')
        Victims.world.defineState(human, 'obs_victim_danger', float)
        human.setState('obs_victim_danger', 0)
        Victims.world.defineState(human, 'obs_victim_reward', float)
        human.setState('obs_victim_reward', 0)
        
    def beliefAboutVictims(human):
        """ Create uncertain beliefs about each victim's properties"""
        for vic in Victims.victimAgents:
            d = Distribution({'unsaved':1,'saved':1,'dead':1})
            d.normalize()
            human.setBelief(stateKey(vic.name, 'status'), d)
            
            d = Distribution({loc:1 for loc in range(locations.Locations.numLocations)})
            d.normalize()            
            human.setBelief(stateKey(vic.name, 'loc'), d)
            
            human.setBelief(stateKey(vic.name, 'savior'), Distribution({'none':1}))
#            human.setBelief(stateKey(vic.name, 'savior'), Distribution({0:1}))


#    def ignoreVictims(human):           
#        """ Remove any victim ground truth from observation
#        """
#        if human.omega == True:
#            omega = {var for var in Victims.world.variables.keys()}
#        else:
#            omega = human.omega
#        for vi in Victims.victimAgents:
#            omega = {var for var in omega if not (isStateKey(var) and (state2agent(var) == vi.name))}
#        human.omega = omega
        
    def makeTriageAction(human):
        """
        Create a triage action per victim
        Legal action if: 1) human and victim are in same location; 2)victim is unsaved
        Action effects: a) if danger is down to 0: 1) victim is saved, 2) victim remembers savior's name       
        b) Always decrement victim's danger
        """        
        Victims.triageActions[human.name] = []
        for victim in Victims.victimAgents:
            ## TODO change to use observed variables
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
            
        Victims.makeVictimReward(human)

    def makeVictimReward(human):
        """
        Human gets reward if: a) victim is saved; b) human is the savior; 
        c) last human action was to save this victim (so reward only obtained once)
        
        """ 
        ## TODO change to use observed variables
        for victim in Victims.victimAgents:
            goal = makeTree({'if': equalRow(stateKey(victim.name,'status'),'saved'),
                            True: {'if': equalRow(stateKey(victim.name, 'savior'), human.name),
                                   True: setToFeatureMatrix(rewardKey(human.name),stateKey(victim.name,'reward')),
                                   False: setToConstantMatrix(rewardKey(human.name),0)},
                            False: setToConstantMatrix(rewardKey(human.name),0)})
            human.setReward(goal,1)
            
   
    def makeNearVDict(victims, humanLocKey, humanObsKey, victimKey, defaultValue):
        """
        Recursively test if human is co-located with any of the victims.
        If True, set humanObsKey to the value of victimKey
        If not co-located with any victim, set humanObsKey to the defaultValue
        """
        if victims == []:
            return setToConstantMatrix(humanObsKey, defaultValue)
        new = {'if': equalFeatureRow(humanLocKey, stateKey(victims[0].name, 'loc')), 
               True: setToFeatureMatrix(humanObsKey, stateKey(victims[0].name, victimKey)), 
               False: Victims.makeNearVDict(victims[1:], humanLocKey, humanObsKey, victimKey, defaultValue)}
        return new
    
    def makeNearVTree(humanLocKey, humanObsKey, victimKey, defaultValue):
        return makeTree(Victims.makeNearVDict(Victims.victimAgents, 
                                                humanLocKey, humanObsKey,
                                                victimKey, defaultValue)) 
    
    def triage(human, victimID):
        Victims.world.step(Victims.triageActions[human.name][victimID])