# -*- coding: utf-8 -*-
"""
The module contains classes and methods for dealing with victims in the ASIST S&R problem. ``fewacts`` refers to the fact that this implementation has "few actions".
"""

from psychsim.pwl import makeTree, setToConstantMatrix, incrementMatrix, setToFeatureMatrix, \
    equalRow, equalFeatureRow, andRow, stateKey, rewardKey, actionKey, isStateKey, state2agent, \
    Distribution, setFalseMatrix, noChangeMatrix, addFeatureMatrix
from helpers import anding

class Victim:
    """ Victim class

    Attributes:
        self.rm: location; room the victim is in
        self.clr: victim "color"; i.e. severity of injuries
        self.expr: expiration; whether victim is expired or not
        self.rew: reward; how much reward is given for rescuing the victim

    """
    def __init__(self, rm, clr, expr, va, rew):
        self.room = rm
        self.color = clr
        self.vicAgent = va
        self.expiry = expr
        self.reward = rew

class Victims:
    """ Methods for modeling victims within a psychsim world.

    Attributes:
        TYPE_REWARDS: How much reward for different color victims
        TYPE_REQD_TIMES: Number of seconds of triage required to save a victim
        TYPE_EXPIRY: Number of seconds until victim dies
        P_EMPTY_FOV: Probability that a player's FOV is empty when stepping into a room
        P_VIC_FOV: To be overwritten based on number of victims in env
        STR_CROSSHAIR_ACT: String label for action of placing victim in crosshair
        STR_APPROACH_ACT: String label for action of approaching victim
        STR_TRIAGE_ACT: String label for triage action
        STR_CROSSHAIR_VAR: String label for the data field that indicates whether a victim is in the crosshair or not
        STR_APPROACH_VAR: String label for the data field that indicates whether the player is near enough the victim to perform a triage action
        STR_FOV_VAR: String label for the data field that indicates whether a victim is within the player's field of view
        FULL_OBS: Observability of domain

        victimsByLocAndColor: A dict mapping a room to a dict mapping a color to the corresponding victim object
        victimAgents: A list of victim objects containing all victims in the world
        triageActions: A map from a player to her triage actions
        crosshairActs: A map from a player to her crosshair actions
        approachActs: A map from a player to her approach actions
        world: link to domain psychsim world


    """

    FULL_OBS = None

    TYPE_REWARDS = {'Green':10, 'Orange':200}
    TYPE_REQD_TIMES = {'Green':1, 'Orange':1}
    TYPE_EXPIRY ={'Green':15*60, 'Orange':7*60}

    P_EMPTY_FOV = 0.5   #: probability that a player's FOV is empty when stepping into a room
    P_VIC_FOV = 0       #: to be overwritten based on number of victims in env

    STR_CROSSHAIR_ACT = 'actCH'
    STR_APPROACH_ACT = 'actApproach'
    STR_TRIAGE_ACT = 'actTriage'
    STR_CROSSHAIR_VAR = 'vicInCH'
    STR_APPROACH_VAR = 'vicApproached'
    STR_FOV_VAR = 'vicInFOV'

    victimsByLocAndColor = {}
    victimAgents = []
    triageActions = {}
    crosshairActs = {}
    approachActs = {}
    world = None

    def makeOrangeGreenVictims(roomsWith1, roomsWith2, humanNames):
        """
        This method puts an orange victim in every room that has 1+ victims
        and a green victim in every room that has 2 victims.

        Parameters:
            roomsWith1: list of rooms with a single victim
            roomsWith2: list of rooms with two victims
            humanNames: ??? -- add this description

        Returns:
            Creates victims in the psychsim world, updates the total number of victims `vi` and adds victims to `vicNames`

        Note:
            The limitation to 2 victims per room with alternate colors is a limitation of the current implementation.
            This will  need to be addressed in the future.

        """
        vi = 0
        roomsWithVics = list(roomsWith1) + list(roomsWith2)
        for r in roomsWithVics:
            Victims._makeVictim(vi, r, 'Orange', humanNames, roomsWithVics)
            vi += 1
        for r in roomsWith2:
            Victims._makeVictim(vi, r, 'Green', humanNames, roomsWithVics)
            vi += 1

        Victims.numVictims = vi
        Victims.vicNames = ['victim'+str(i) for i in range(Victims.numVictims)]

    def makeVictims(vLocations, vTypes, humanNames, locationNames):
        """
        Method for creating victims in the world

        Parameters:
            vLocations: list of locations of victims
            vTypes: list containing the type of each victim
            humanNames: ??? --- add this description
            locationNames:
        """
        assert(len(vLocations) == len(vTypes))
        Victims.numVictims = len(vTypes)
        Victims.vicNames = ['victim'+str(i) for i in range(Victims.numVictims)]
        for vi in range(Victims.numVictims):
            loc = vLocations[vi]
            vtype = vTypes[vi]
            Victims._makeVictim(vi, loc, vtype, humanNames, locationNames)

    def _makeVictim(vi, loc, vtype, humanNames, locationNames):
            victim = Victims.world.addAgent('victim' + str(vi))

            Victims.world.defineState(victim.name,'status',list,['unsaved','saved','dead'])
            victim.setState('status','unsaved')

            Victims.world.defineState(victim.name,'danger',float,description='How far victim is from health')
            victim.setState('danger', Victims.TYPE_REQD_TIMES[vtype])

            Victims.world.defineState(victim.name,'reward',int,description='Value earned by saving this victim')
            rew = Victims.TYPE_REWARDS[vtype]
            victim.setState('reward', rew)

            Victims.world.defineState(victim.name,'loc',list, locationNames)
            victim.setState('loc', loc)

            Victims.world.defineState(victim.name,'savior',list, ['none'] + humanNames, description='Name of agent who saved me, if any')
            victim.setState('savior', 'none')

            vicObj = Victim(loc, vtype, Victims.TYPE_EXPIRY[vtype], victim, rew)
            Victims.victimAgents.append(vicObj)

            if loc not in Victims.victimsByLocAndColor.keys():
                Victims.victimsByLocAndColor[loc] = {}
            Victims.victimsByLocAndColor[loc][vtype] = vicObj

    def getVicName(loc, color):
        if color not in Victims.victimsByLocAndColor[loc].keys():
            print('ERROR. No', color, 'victim in', loc)
            return ''
        return Victims.victimsByLocAndColor[loc][color].vicAgent.name

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

        for vicObj in Victims.victimAgents:
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

    def makePreTriageActions(human):
        """
        Create ONE action to approach victim and ONE action to place them in crosshair
        Legal if: there is a victim in FoV
        Action effects: set the crosshair/approached var to the victim in FoV
        """
        # create and initialize crosshair/approached vars
        for varname in [Victims.STR_APPROACH_VAR, Victims.STR_CROSSHAIR_VAR, Victims.STR_FOV_VAR]:
            Victims.world.defineState(human.name,varname,list, ['none'] + Victims.vicNames)
            human.setState(varname,'none')

        # Legal if there's a victim in your field of view
        legalityTree = makeTree({'if': equalRow(stateKey(human.name, Victims.STR_FOV_VAR), 'none'),
                                 True: False,
                                 False: True})
        crossHairAction = human.addAction({'verb': Victims.STR_CROSSHAIR_ACT}, legalityTree)
        getCloseAction = human.addAction({'verb': Victims.STR_APPROACH_ACT}, legalityTree)

        # Dynamics: Each of the 2 pre-triage actions sets the corresponding variable
        # to the value of the victim in FOV
        fovKey = stateKey(human.name, Victims.STR_FOV_VAR)
        for act, varname in zip([crossHairAction, getCloseAction],
                                [Victims.STR_CROSSHAIR_VAR, Victims.STR_APPROACH_VAR]):
            key = stateKey(human.name, varname)
            tree = makeTree(setToFeatureMatrix(key, fovKey))
            Victims.world.setDynamics(key, act, tree)

        Victims.crosshairActs[human.name] = crossHairAction
        Victims.approachActs[human.name] = getCloseAction

    def makeTriageAction(human):
        """
        Create ONE triage action
        Legal action if: 1) non-null victim in crosshairs and same as victim within distance
        2) victim is unsaved
        Action effects: a) if danger is down to 0: 1) victim is saved, 2) victim remembers savior's name
        b) Always decrement victim's danger

        """

        crossKey = stateKey(human.name, Victims.STR_CROSSHAIR_VAR)
        approachKey = stateKey(human.name, Victims.STR_APPROACH_VAR)

        testAllVics = {'if': equalRow(crossKey, ['none'] + Victims.vicNames),
                       0: False}
        for i, vn in enumerate(Victims.vicNames):
            testAllVics[i+1] = {'if': equalRow(stateKey(vn, 'status'), 'unsaved'),
                                 True: True, False: False}
        legalityTree = makeTree({'if': equalFeatureRow(crossKey, approachKey),
                        True: testAllVics,
                        False: False})
        action = human.addAction({'verb': 'triage', }, legalityTree)

        for vicObj in Victims.victimAgents:
            victim = vicObj.vicAgent
            statusKey = stateKey(victim.name,'status')
            dangerKey = stateKey(victim.name,'danger')
            saviorKey = stateKey(victim.name,'savior')

            ## Status: if danger is down to 0, victim is saved
            tree = makeTree({'if': equalRow(crossKey, victim.name),
                             True: {'if': equalRow(dangerKey, 1),
                                    True: setToConstantMatrix(statusKey, 'saved'),
                                    False: setToConstantMatrix(statusKey, 'unsaved')},
                            False: noChangeMatrix(statusKey)})
            Victims.world.setDynamics(statusKey,action,tree)

            ## Savior name: if danger is down to 0, set to human's name. Else none
            tree = makeTree({'if': equalRow(crossKey, victim.name),
                             True: {'if': equalRow(dangerKey, 1),
                                 True: setToConstantMatrix(saviorKey, human.name),
                                 False:setToConstantMatrix(saviorKey, 'none')},
                            False: noChangeMatrix(saviorKey)})
            Victims.world.setDynamics(saviorKey,action,tree)

            ## Danger: dencrement danger by 1
            tree = makeTree({'if': equalRow(crossKey, victim.name),
                             True: incrementMatrix(dangerKey,-1),
                             False: noChangeMatrix(dangerKey)})
            Victims.world.setDynamics(dangerKey,action,tree)

        Victims.triageActions[human.name] = action
        Victims.makeVictimReward(human)

    def makeVictimReward(human):
        """ ADD DESCRIPTION HERE

        Human gets reward if:

        a) victim is saved;
        b) human is the savior;
        c) last human action was triage (so reward only obtained once)

        """
        rKey = rewardKey(human.name)
        crossKey = stateKey(human.name, Victims.STR_CROSSHAIR_VAR)
        testAllVics = {'if': equalRow(crossKey, ['none'] + Victims.vicNames),
                       0: noChangeMatrix(rKey)}
        for i, vobj in enumerate(Victims.victimAgents):
            vn = vobj.vicAgent.name
            testAllVics[i+1] = anding([equalRow(stateKey(vn,'status'),'saved'),
                                       equalRow(stateKey(vn, 'savior'), human.name),
                                       equalRow(actionKey(human.name), Victims.triageActions[human.name])],
                                incrementMatrix(rKey, vobj.reward),
                                noChangeMatrix(rKey))
        human.setReward(makeTree(testAllVics),1)

    def getTriageAction(human):
        if type(human) == str:
            name = human
        else:
            name = human.name
        return Victims.triageActions[name]

    def getPretriageAction(human, acts):
        if type(human) == str:
            name = human
        else:
            name = human.name
        return acts[name]

    def approach(human):
        Victims.world.step(Victims.getPretriageAction(human, Victims.approachActs))

    def putInCH(human):
        Victims.world.step(Victims.getPretriageAction(human, Victims.crosshairActs))

    def triage(human):
        Victims.world.step(Victims.getTriageAction(human))
