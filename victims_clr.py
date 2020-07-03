# -*- coding: utf-8 -*-
"""
The module contains classes and methods for dealing with victims in the ASIST S&R problem. ``fewacts`` refers to the fact that this implementation has "few actions".
"""

from psychsim.pwl import makeTree, setToConstantMatrix, incrementMatrix, setToFeatureMatrix, \
    equalRow, equalFeatureRow, andRow, stateKey, rewardKey, actionKey, isStateKey, state2agent, \
    Distribution, setFalseMatrix, noChangeMatrix, addFeatureMatrix, makeFuture, trueRow
from helpers import anding, oring

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
        COLOR_REWARDS: How much reward for different color victims
        COLOR_REQD_TIMES: Number of seconds of triage required to save a victim
        COLOR_EXPIRY: Number of seconds until victim dies
        COLOR_PRIOR_P_P: Probability of a victim of a given color being present in a room
        COLOR_FOV_P: Probability that a player's FOV has a victim of a given color after a search action 
        
        STR_CROSSHAIR_ACT: String label for action of placing victim in crosshair
        STR_APPROACH_ACT: String label for action of approaching victim
        STR_TRIAGE_ACT: String label for triage action
        
        STR_CROSSHAIR_VAR: String label for the data field that indicates color of victim in the crosshair
        STR_APPROACH_VAR: String label for the data field that indicates color of approached victim
        STR_FOV_VAR: String label for the data field that indicates color of victim in FOV
        
        FULL_OBS: Observability of domain

        victimsByLocAndColor: A dict mapping a room to a dict mapping a color to the corresponding victim object
        victimAgents: A list of victim objects containing all victims in the world
        
        triageActs: A map from a player to her triage actions
        crosshairActs: A map from a player to her crosshair actions
        approachActs: A map from a player to her approach actions
        searchActs: A map from a player to her search actions
        
        world: link to domain psychsim world

    """

    FULL_OBS = None

    COLORS = ['Green', 'Gold', 'Red', 'White']
    COLOR_REWARDS = {'Green':10, 'Gold':200}
    COLOR_REQD_TIMES = {'Green':1, 'Gold':1}
    COLOR_EXPIRY = {'Green':15*60, 'Gold':7.5*60}
    COLOR_PRIOR_P = {'Green':0, 'Gold':0}
    COLOR_FOV_P = {'Green':0, 'Gold':0, 'Red':0, 'White':0}

    STR_CROSSHAIR_ACT = 'actCH'
    STR_APPROACH_ACT = 'actApproach'
    STR_TRIAGE_ACT = 'actTriage'

    STR_CROSSHAIR_VAR = 'vicInCH'
    STR_APPROACH_VAR = 'vicApproached'
    STR_FOV_VAR = 'vicInFOV'

    victimsByLocAndColor = {}
    victimAgents = []

    triageActs = {}
    crosshairActs = {}
    approachActs = {}
    searchActs = {}
    world = None

    def makeGoldGreenVictims(roomsWith1, roomsWith2, humanNames):
        """
        This method puts an Gold victim in every room that has 1+ victims
        and a green victim in every room that has 2 victims.

        Parameters:
            roomsWith1: list of rooms with a single victim
            roomsWith2: list of rooms with two victims
            humanNames: list of agent names that constitute legal values for the `savior` state of each victim

        Returns:
            Creates victims in the psychsim world, updates the total number of victims `vi` and adds victims to `vicNames`

        Note:
            The limitation to 2 victims per room with alternate colors is a limitation of the current implementation.
            This will  need to be addressed in the future.

        """
        vi = 0
        roomsWithVics = list(roomsWith1) + list(roomsWith2)
        for r in roomsWithVics:
            Victims._makeVictim(vi, r, 'Gold', humanNames, roomsWithVics)
            vi += 1
        for r in roomsWith2:
            Victims._makeVictim(vi, r, 'Green', humanNames, roomsWithVics)
            vi += 1

        Victims.numVictims = vi
        Victims.vicNames = ['victim'+str(i) for i in range(Victims.numVictims)]

    def makeVictims(vLocations, colors, humanNames, locationNames):
        """Method for creating victims in the world

        Parameters:
            vLocations: list of locations of victims
            colors: list containing the color of each victim
            humanNames: list of agent names that constitute legal values for the `savior` state of each victim
            locationNames: list of location names that constitute legal values for the `loc` state of each victim
        Returns:
            Creates victim agents, and adds them to the world. Adds each victim to the `Victims.victimAgents` list, and also to the `Victims.victimsByLocAndColor` dictionary.
        """
        assert(len(vLocations) == len(colors))
        Victims.numVictims = len(colors)
        Victims.vicNames = ['victim'+str(i) for i in range(Victims.numVictims)]
        for vi in range(Victims.numVictims):
            loc = vLocations[vi]
            color = colors[vi]
            Victims._makeVictim(vi, loc, color, humanNames, locationNames)

    def _makeVictim(vi, loc, color, humanNames, locationNames):
        victim = Victims.world.addAgent('victim' + str(vi))

        Victims.world.defineState(victim.name,'color',list,['Gold','Green','Red', 'White'])
        victim.setState('color',color)

        Victims.world.defineState(victim.name,'danger',float,description='How far victim is from health')
        victim.setState('danger', Victims.COLOR_REQD_TIMES[color])

        Victims.world.defineState(victim.name,'reward',int,description='Value earned by saving this victim')
        rew = Victims.COLOR_REWARDS[color]
        victim.setState('reward', rew)

        Victims.world.defineState(victim.name,'loc',list, locationNames)
        victim.setState('loc', loc)

        Victims.world.defineState(victim.name,'savior',list, ['none'] + humanNames, description='Name of agent who saved me, if any')
        victim.setState('savior', 'none')

        vicObj = Victim(loc, color, Victims.COLOR_EXPIRY[color], victim, rew)
        Victims.victimAgents.append(vicObj)

        if loc not in Victims.victimsByLocAndColor.keys():
            Victims.victimsByLocAndColor[loc] = {}
        Victims.victimsByLocAndColor[loc][color] = vicObj

    def setupTriager(VICTIMS_LOCS, VICTIM_TYPES, triageAgent, locations):
        ## Create booleans for whether I just saved a green/gold victim
        for color in Victims.COLOR_REQD_TIMES.keys():
            key = Victims.world.defineState(triageAgent.name, 'saved_' + color, bool)
            Victims.world.setFeature(key, False)

        Victims.makeVictims(VICTIMS_LOCS, VICTIM_TYPES, [triageAgent.name], locations)
        Victims.makePreTriageActions(triageAgent)
        Victims.makeTriageAction(triageAgent)
        ## TODO: insert victim sensor creation here


    def getVicName(loc, color):
        if color not in Victims.victimsByLocAndColor[loc].keys():
            print('ERROR. No', color, 'victim in', loc)
            return ''
        return Victims.victimsByLocAndColor[loc][color].vicAgent.name

    def getUnObsName(loc,color):
        return 'unobs' + loc+'_'+color

    def createObsVars4Victims(human, allLocations):
        """
        Create a boolean per room per victim color.
        room_color=T means player knows this color victim is in room.
        room_color=F means player knows this color victim is not in room.
        Use a prior over P(room_color=T)
        """
        ks = []
        ds = []
        for loc in allLocations:
            for color in Victims.COLOR_PRIOR_P.keys():
                ks.append(Victims.world.defineState(human.name, Victims.getUnObsName(loc,color), bool))
                ds.append(Distribution({True:Victims.COLOR_PRIOR_P[color], False:1-Victims.COLOR_PRIOR_P[color]}))
                # dp: Set true value on world state
                Victims.world.setFeature(ks[-1],loc in Victims.victimsByLocAndColor and color in Victims.victimsByLocAndColor[loc])

        if not Victims.FULL_OBS:
            for i, (key,dist) in enumerate(zip(ks,ds)):
            	human.setBelief(key, dist)

    def normalizeD(d, key):
        sammy = sum(d.values())
        nd = {c:p/sammy for c,p in d.items()}
        return [(setToConstantMatrix(key, c), p) for c,p in nd.items()]

    def makeAllFOVDistrs(fovKey, numVicsInRoom, default=0):
        if numVicsInRoom == 0:
            d = {c:default for c in Victims.COLORS if default > 0}
            d['none'] = 1
            return Victims.normalizeD(d, fovKey)

        if numVicsInRoom == 1:
            allDs = dict()
            for c1 in Victims.COLORS:
                d = {c:default for c in Victims.COLORS if default > 0}
                d[c1] = Victims.COLOR_FOV_P[c1]
                d['none'] = 1 - sum(d.values())
                allDs[c1] = Victims.normalizeD(d, fovKey)
            return allDs

        if numVicsInRoom == 2:
            allDs = dict()
            for c1 in Victims.COLORS:
                allDs[c1] = dict()
                for c2 in Victims.COLORS:
                    d = {c:default for c in Victims.COLORS if default > 0}
                    if c1 == c2:
                        d[c1] = 2 * Victims.COLOR_FOV_P[c1]
                    else:
                        d[c1] = Victims.COLOR_FOV_P[c1]
                        d[c2] = Victims.COLOR_FOV_P[c2]
                    d['none'] = 1 - sum(d.values())
                    allDs[c1][c2] = Victims.normalizeD(d, fovKey)
            return allDs

    def makeSearchAction(human, allLocations):
        dynTrees = dict()
        action = human.addAction({'verb': 'search'})

        fovKey  = stateKey(human.name, Victims.STR_FOV_VAR)
        fovTree = {'if': equalRow(stateKey(human.name, 'loc'), allLocations)}
        for il, loc in enumerate(allLocations):
            if loc not in Victims.victimsByLocAndColor.keys():
                dist = Victims.makeAllFOVDistrs(fovKey, 0)
                if len(dist) > 1:
                    fovTree[il] = {'distribution': dist}
                else:
                    fovTree[il] = dist[0][0]
                continue
            # Get IDs of victims in this room
            vicsHere = Victims.victimsByLocAndColor[loc].values()
            vicsHereNames = [v.vicAgent.name for v in vicsHere]
            numVicsInLoc = len(vicsHereNames)
            allDistributions = Victims.makeAllFOVDistrs(fovKey, numVicsInLoc)
            if numVicsInLoc == 1:
                v0Color = stateKey(vicsHereNames[0], 'color')
                fovTree[il] = {'if':equalRow(v0Color, Victims.COLORS)}
                for ic,c0 in enumerate(Victims.COLORS):
                    if len(allDistributions[c0]) > 1:
                        fovTree[il][ic] = {'distribution': allDistributions[c0]}
                    else:
                        fovTree[il][ic] = allDistributions[c0][0][0]
            if numVicsInLoc == 2:
                v0Color = stateKey(vicsHereNames[0], 'color')
                v1Color = stateKey(vicsHereNames[1], 'color')
                fovTree[il] = {'if':equalRow(v0Color, Victims.COLORS)}
                for ic0,c0 in enumerate(Victims.COLORS):
                    fovTree[il][ic0] = {'if': equalRow(v1Color, Victims.COLORS)}
                    for ic1,c1 in enumerate(Victims.COLORS):
                        if len(allDistributions[c0][c1]) > 1:
                            fovTree[il][ic0][ic1] = {'distribution': allDistributions[c0][c1]}
                        else:
                            fovTree[il][ic0][ic1] = allDistributions[c0][c1][0][0]

        Victims.world.setDynamics(fovKey,action,makeTree(fovTree))

        ## For every location and victim color, if this color is in (future) FOV and player in loc,
        ## set the corresponding observed variable to True
        locKey = stateKey(human.name, 'loc')
        newFov = makeFuture(fovKey)
        for loc in allLocations:
            for color in ['Gold', 'Green']:
                obsVicColorKey = stateKey(human.name, Victims.getUnObsName(loc,color))
                tree = anding([equalRow(locKey, loc), equalRow(newFov, color)],
                               setToConstantMatrix(obsVicColorKey, True),
                               noChangeMatrix(obsVicColorKey))
                Victims.world.setDynamics(obsVicColorKey,action,makeTree(tree))
                dynTrees[Victims.getUnObsName(loc,color)] = tree

        ## Reset CH and approached victim variables to None
        for varname in [Victims.STR_APPROACH_VAR, Victims.STR_CROSSHAIR_VAR]:
            vtKey = stateKey(human.name, varname)
            tree = makeTree(setToConstantMatrix(vtKey, 'none'))
            Victims.world.setDynamics(vtKey,True,tree)

        Victims.searchActs[human.name] = action
        Victims.resetJustSavedFlags(human, action)

        ## this structure is just for debugging
        dynTrees['fov'] = fovTree
        return dynTrees

    def makePreTriageActions(human):
        """
        Create ONE action to approach victim and ONE action to place them in crosshair
        Legal if: there is a victim in FoV
        Action effects: set the crosshair/approached var to the victim in FoV
        """
        # create and initialize fov/crosshair/approached vars
        for varname in [Victims.STR_APPROACH_VAR, Victims.STR_CROSSHAIR_VAR, Victims.STR_FOV_VAR]:
            Victims.world.defineState(human.name,varname,list, ['none'] + Victims.COLORS)
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
        Victims.resetJustSavedFlags(human, crossHairAction)
        Victims.resetJustSavedFlags(human, getCloseAction)

    def resetJustSavedFlags(human, action):
        for color in Victims.COLOR_REQD_TIMES.keys():
            key = stateKey(human.name, 'saved_' + color)
            tree = makeTree(setToConstantMatrix(key, False))
            Victims.world.setDynamics(key, action, tree)

    def makeTriageAction(human):
        """
        Create ONE triage action
        Legal action if:
        1) victim in crosshairs same as victim approached and
        2) victim in crosshairs is Gold or Green

        Action effects: For every loc, color, the corresponding victim's state is changed
        if player is in that location and CH victim is that color
        a) if danger is down to 0: 1) victim is saved, 2) victim remembers savior's name
        b) Always decrement victim's danger
        """
        crossKey = stateKey(human.name, Victims.STR_CROSSHAIR_VAR)
        approachKey = stateKey(human.name, Victims.STR_APPROACH_VAR)
        locKey = stateKey(human.name, 'loc')

        legal = {'if': equalFeatureRow(crossKey, approachKey),
                 True: oring([equalRow(crossKey, 'Gold'), equalRow(crossKey, 'Green')],
                              True, False),
                 False: False}
        action = human.addAction({'verb': 'triage'}, makeTree(legal))

        for loc in Victims.victimsByLocAndColor.keys():
            for color in Victims.victimsByLocAndColor[loc].keys():
                vicObj = Victims.victimsByLocAndColor[loc][color]
                victim = vicObj.vicAgent
                colorKey = stateKey(victim.name,'color')
                dangerKey = stateKey(victim.name,'danger')
                saviorKey = stateKey(victim.name,'savior')

                ## Color: if danger is down to 0, victim turns white
                tree = makeTree(anding([equalRow(crossKey, color),
                                        equalRow(locKey, loc),
                                        equalRow(dangerKey, 1)],
                                        setToConstantMatrix(colorKey, 'White'),
                                        noChangeMatrix(colorKey)))
                Victims.world.setDynamics(colorKey,action,tree)

                ## Did I save a victim victim of this color?
                savedKey = stateKey(human.name, 'saved_'+color)
                tree = makeTree(anding([equalRow(crossKey, color),
                                        equalRow(locKey, loc),
                                        equalRow(dangerKey, 1)],
                                        setToConstantMatrix(savedKey, True),
                                        noChangeMatrix(savedKey)))
                Victims.world.setDynamics(savedKey,action,tree)

                ## Color in FOV, CH, approached: if victim I'm aiming at turns white
                ## reflect change in these 3 variables
                for varname in [Victims.STR_APPROACH_VAR, Victims.STR_CROSSHAIR_VAR, Victims.STR_FOV_VAR]:
                    k = stateKey(human.name, varname)
                    tree = makeTree(anding([equalRow(crossKey, color),
                                            equalRow(locKey, loc),
                                            equalRow(makeFuture(colorKey), 'White')],
                                            setToConstantMatrix(k, 'White'),
                                            noChangeMatrix(k)))
                    Victims.world.setDynamics(k,action,tree)

                ## Savior name: if danger is down to 0, set to human's name. Else none
                tree = makeTree(anding([equalRow(crossKey, color),
                                        equalRow(locKey, loc),
                                        equalRow(dangerKey, 1)],
                                        setToConstantMatrix(saviorKey, human.name),
                                        noChangeMatrix(saviorKey)))
                Victims.world.setDynamics(saviorKey,action,tree)

                ## Danger: dencrement danger by 1
                tree = makeTree(anding([equalRow(crossKey, color),
                                        equalRow(locKey, loc)],
                                        incrementMatrix(dangerKey,-1),
                                        noChangeMatrix(dangerKey)))
                Victims.world.setDynamics(dangerKey,action,tree)

        Victims.triageActs[human.name] = action
        Victims.makeVictimReward(human)

    @staticmethod
    def makeVictimReward(agent, model=None, rwd_dict=None):
        """ Human gets reward if flag is set
        """
        rKey = rewardKey(agent.name)
        rtree = nested_tree = {}
        for color in Victims.COLOR_REQD_TIMES.keys():
            rwd = rwd_dict[color] if rwd_dict is not None and color in rwd_dict else Victims.COLOR_REWARDS[color]
            key = stateKey(agent.name, 'saved_' + color)
            if len(nested_tree) > 0 and False not in nested_tree:
                nested_tree[False] = {}
                nested_tree = nested_tree[False]
            nested_tree['if'] = trueRow(key)
            nested_tree[True] = setToConstantMatrix(rKey, rwd)

        if len(rtree) > 0:
            nested_tree[False] = noChangeMatrix(rKey)

        agent.setReward(makeTree(rtree), 1, model)

    def old_makeVictimReward(human):
        """ Human gets reward if:
        a) victim is white;
        b) human is the savior;
        c) last human action was triage (so reward only obtained once)
        """
        rKey = rewardKey(human.name)
        locKey = stateKey(human.name, 'loc')
        for loc in Victims.victimsByLocAndColor.keys():
            for color in Victims.victimsByLocAndColor[loc].keys():
                victim = Victims.victimsByLocAndColor[loc][color].vicAgent
                colorKey = stateKey(victim.name,'color')
                saviorKey = stateKey(victim.name,'savior')

                rtree = anding([equalRow(colorKey,'White'),
                                equalRow(saviorKey, human.name),
                                equalRow(locKey, loc),
                                equalRow(actionKey(human.name), Victims.triageActs[human.name])],
                                setToConstantMatrix(rKey, Victims.COLOR_REWARDS[color]),
                                noChangeMatrix(rKey))
                human.setReward(makeTree(rtree),1)

    def getTriageAction(human):
        if type(human) == str:
            name = human
        else:
            name = human.name
        return Victims.triageActs[name]

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

    def search(human, s):
        Victims.world.step(Victims.searchActs[human.name], select=s)
