# -*- coding: utf-8 -*-
"""
Created on Thu Feb 20 11:23:22 2020

@author: mostafh
"""

from psychsim.pwl import makeTree, setToConstantMatrix, incrementMatrix, setToFeatureMatrix, \
    equalRow, equalFeatureRow, andRow, stateKey, rewardKey, actionKey, isStateKey, state2agent, \
    Distribution, setFalseMatrix, noChangeMatrix, addFeatureMatrix
from psychsim.reward import achieveFeatureValue
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
    TYPE_REWARDS = {'Green':10, 'Orange':200}
    # Number of triage seconds to save a victim
    TYPE_REQD_TIMES = {'Green':1, 'Orange':1}
    # Number of seconds after which a victim dies
    TYPE_EXPIRY ={'Green':15*60, 'Orange':7*60}

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

    def makePreTriageLegality(victim,human,sKeyName,preTriageActionName,initialValue):
        # if victim and player are in the same location
        vLoc = stateKey(victim.name, sKeyName)
        hLoc = stateKey(human.name, sKeyName)

        key = stateKey(human.name, preTriageActionName)

        legalityTree = makeTree({'if': equalFeatureRow(vLoc,hLoc),
                                    True: {'if': equalRow(key,initialValue),
                                        True: True,
                                        False: False},
                                    False: False})
        return legalityTree, key

    def makePreTriageActions(human):
        """
        Create pre-triage actions per victim
        Legal actions if: Human and victim are in same location;
        Action effects: move within correct distance, or put victim in crosshair
        """

        # create a within range flag
        inRange = 'victim within range'
        Victims.world.defineState(human.name,inRange,bool)
        human.setState(inRange,False)

        # create a 'victim targeted' state that must be true for triage to be successful
        crossHair = 'victim in crosshair'
        Victims.world.defineState(human.name,crossHair,bool)
        human.setState(crossHair,False)

        for room in Victims.victimAgents.keys():
            for vicColor, vicObj in Victims.victimAgents[room].items():
                victim = vicObj.vicAgent

                ##########
                # vic_target action
                vtLegalityTree, vtKey = Victims.makePreTriageLegality(victim,human,'loc',crossHair,False)

                vtAction = human.addAction({'verb': 'target victim', 'object':victim.name}, vtLegalityTree)

                # dynamics
                # Change 'victim tareted' to True when making the 'target victim' action
                vtTree = makeTree(setToConstantMatrix(vtKey,True))
                Victims.world.setDynamics(vtKey,vtAction,vtTree)

                Victims.preTriageActions[human.name][room][vicColor] = vtAction

                ##########
                # victim within range
                crLegalityTree, crKey = Victims.makePreTriageLegality(victim,human,'loc',inRange,False)

                crAction = human.addAction({'verb': 'move within range', 'object':victim.name}, crLegalityTree)

                # dynamics
                # Change 'victim tareted' to True when making the 'target victim' action
                crTree = makeTree(setToConstantMatrix(crKey,True))
                Victims.world.setDynamics(crKey,crAction,crTree)

                Victims.preTriageActions[human.name][room][vicColor] = crAction

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
                                        True: {'if': equalRow(stateKey(human.name, 'victim in crosshair'), True),
                                            True: {'if': equalRow(stateKey(human.name, 'victim within range'), True),
                                                True: {'if': equalRow(stateKey(victim.name, 'status'), 'unsaved'),
                                                    True: True,
                                                    False: False},
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
        Human gets reward if: a) victim is saved; b) victim and human collcated; c) human is the savior;
        d) last human action was to save this victim (so reward only obtained once),

        """
        rKey = rewardKey(human.name)

        for room in Victims.victimAgents.keys():
            for vicColor, vicObj in Victims.victimAgents[room].items():
                victim = vicObj.vicAgent
                rwd = Victims.TYPE_REWARDS[vicColor]

                goal = achieveFeatureValue(stateKey(victim.name,'savior'), human.name, human.name)
                human.setReward(goal,rwd)

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
        if type(human) == str:
            name = human
        else:
            name = human.name
        return Victims.triageActions[name][room][vicColor]

    def triage(human, room, vicColor):
        Victims.world.step(Victims.makeTriageAction(human, room, vicColor))

    def getPretriageAction(human, room, vicColor):
        if type(human) == str:
            name = human
        else:
            name = human.name
        return Victims.preTriageActions[name][room][vicColor]

    def pre_triage(human, room, vicColor):
        Victims.world.step(Victims.getPretriageAction(human, room, vicColor))
