# -*- coding: utf-8 -*-
"""
Created on Thu Feb 20 11:23:22 2020

@author: mostafh
"""

from psychsim.pwl import makeTree, setToConstantMatrix, incrementMatrix, setToFeatureMatrix, \
    equalRow, equalFeatureRow, andRow, stateKey, rewardKey, actionKey, isStateKey, state2agent, \
    Distribution, setFalseMatrix, noChangeMatrix, addFeatureMatrix
import new_locations

class Victim:
    def __init__(self, rm, clr, expr, va):
        self.room = rm
        self.color = clr
        self.vicAgent = va
        self.expiry = expr

class Victims:
    FULL_OBS = None
    ## Reward per victim type
    TYPE_REWARDS = [10, 200]
    # number of triage actions needed to restore victim to health
    TYPE_REQD_TIMES = [1, 1]
    TYPE_EXPIRY = [15*60, 7*60]
    VictimTypes = []

    # A dict mapping a room to a dict mapping a color to the corresponding victim object
    victimAgents = {}
    # A dict mapping a human to a dict mapping room to a dict mapping a color to the corresponding action
    triageActions = {}
    # A dict mapping a human to a dict mapping a room to a dict mapping a color to the corresponding action
    preTriageActions = {}
    world = None

    def makeVictims(vLocations, vTypes, humanNames, locationNames):
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

            Victims.world.defineState(victim.name,'loc',list, locationNames)
            victim.setState('loc', vLocations[vi])

            Victims.world.defineState(victim.name,'savior',list, ['none'] + humanNames, description='Name of agent who saved me, if any')
            victim.setState('savior', 'none')

            if vLocations[vi] not in Victims.victimAgents.keys():
                Victims.victimAgents[vLocations[vi]] = {}
            Victims.victimAgents[vLocations[vi]][vTypes[vi]] = Victim(vLocations[vi], vTypes[vi],\
                                 Victims.TYPE_EXPIRY[vTypes[vi]], victim)
            
        # When done initalizing all victims, initialize action data structures
        for humanN in humanNames:
            Victims.preTriageActions[humanN] = {}
            Victims.triageActions[humanN] = {}
            for room in Victims.victimAgents.keys():
                Victims.preTriageActions[humanN][room] = {}
                Victims.triageActions[humanN][room] = {}
                for vic in Victims.victimAgents[room].keys():
                    Victims.preTriageActions[humanN][room][vic] = None
                    Victims.triageActions[humanN][room][vic] = None

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

    def beliefAboutVictims(human, initHumanLoc):
        """ 
        Create uncertain beliefs about each victim's properties. For each victim:
        A) If human's initial location = victim initial's location, human knows victim is right there
        B) If human's initial location != victim initial's location, human assigns 0 belief to victim being in human's init loc
        """
        
        for room in Victims.victimAgents.keys():
            for vicObj in Victims.victimAgents[room].items():
                vic = vicObj.vicAgent
                d = Distribution({'unsaved':1,'saved':1,'dead':1})
                d.normalize()
                human.setBelief(stateKey(vic.name, 'status'), d)
                
                initVicLoc = vicObj.room
                
                if initVicLoc == initHumanLoc:
                    d = Distribution({initVicLoc:1})
                    human.setBelief(stateKey(vic.name, 'loc'), d)
                else:
                    d = Distribution({loc:1 for loc in new_locations.Locations.AllLocations if not loc==initHumanLoc})
                    d.normalize()
                    human.setBelief(stateKey(vic.name, 'loc'), d)
    
                human.setBelief(stateKey(vic.name, 'savior'), Distribution({'none':1}))

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
    def makePreTriageAction(human):
        """
        Create a pre-triage action per victim
        Legal action if: Human and victim are in same location;
        Action effects: Always decrement victim's danger
        """
        
        # create a 'victim targeted' state that must be true for triage to be successful
        Victims.world.defineState(human.name,'vic_targeted',bool)
        human.setState('vic_targeted',False)
        
        for room in Victims.victimAgents.keys():
            for vicColor, vicObj in Victims.victimAgents[room].items():
                victim = vicObj.vicAgent
                # vic_target action
                # if victim and player are in the same location
                v_loc = stateKey(victim.name, 'loc')
                h_loc = stateKey(human.name, 'loc')
    
                vtKey = stateKey(human.name, 'vic_targeted')
    
                vt_legalityTree = makeTree({'if': equalFeatureRow(v_loc,h_loc),
                                            True: {'if': equalRow(vtKey,False),
                                                True: True,
                                                False: False},
                                            False: False})
    
                vt_action = human.addAction({'verb': 'target victim', 'object':victim.name}, vt_legalityTree)
    
                ## Change 'victim tareted' to True when making the 'target viction' action
                vtTree = makeTree(setToConstantMatrix(vtKey,True))
                Victims.world.setDynamics(vtKey,vt_action,vtTree)
    
                Victims.preTriageActions[human.name][room][vicColor] = vt_action
    
    def makeTriageAction(human):
        """
        Create a triage action per victim
        Legal action if: 1) human and victim are in same location; 2)victim is unsaved
        Action effects: a) if danger is down to 0: 1) victim is saved, 2) victim remembers savior's name
        b) Always decrement victim's danger
        ALSO: add a pre-triage condition to the human
        """

        for room in Victims.victimAgents.keys():
            for vicColor, vicObj in Victims.victimAgents[room].items():
                victim = vicObj.vicAgent
                # triage action
                v_loc = stateKey(victim.name, 'loc')
                h_loc = stateKey(human.name, 'loc')
    
                legalityTree = makeTree({'if': equalFeatureRow(v_loc,h_loc),
                                        True: {'if': equalRow(stateKey(human.name, 'vic_targeted'), True),
                                            True: {'if': equalRow(stateKey(victim.name, 'status'), 'unsaved'),
                                                True: True,
                                                False: False},
                                            False: False},
                                        False: False})
                action = human.addAction({'verb': 'triage', 'object':victim.name}, legalityTree)
    
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
                
                Victims.triageActions[human.name][room][vicColor] = action
    
        Victims.makeVictimReward(human)

    def makeVictimReward(human):
        """
        Human gets reward if: a) victim is saved; b) human is the savior;
        c) last human action was to save this victim (so reward only obtained once),

        """
        rkey = rewardKey(human.name)
        for room in Victims.victimAgents.keys():
            for vicColor, vicObj in Victims.victimAgents[room].items():
                victim = vicObj.vicAgent
                rval = stateKey(victim.name, 'reward')
                goal = makeTree({'if': equalRow(stateKey(victim.name,'status'),'saved'),
                                True: {'if': equalRow(stateKey(victim.name, 'savior'), human.name),
                                    True: {'if': equalRow(actionKey(human.name), \
                                                          Victims.triageActions[human.name][room][vicColor]),
                                        True: addFeatureMatrix(rkey,rval),
                                        False: noChangeMatrix(rkey)},
                                    False: noChangeMatrix(rkey)},
                                False: setToConstantMatrix(rkey,0)})
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

    def getTriageAction(human, room, vicColor):
        return Victims.triageActions[human.name][room][vicColor]

    def triage(human, room, vicColor):
        Victims.world.step(Victims.makeTriageAction(human, room, vicColor))

    def getPretriageAction(human, room, vicColor):
        return Victims.preTriageActions[human.name][room][vicColor]

    def pre_triage(human, room, vicColor):
        Victims.world.step(Victims.getPretriageAction(human, room, vicColor))
