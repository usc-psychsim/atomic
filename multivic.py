# -*- coding: utf-8 -*-
"""
The module contains classes and methods for dealing with victims in the ASIST S&R problem. ``fewacts`` refers to the fact that this implementation has "few actions".
"""

from psychsim.pwl import makeTree, setToConstantMatrix, incrementMatrix, setToFeatureMatrix, \
    equalRow, equalFeatureRow, andRow, stateKey, rewardKey, actionKey, isStateKey, state2agent, \
    Distribution, setFalseMatrix, noChangeMatrix, addFeatureMatrix, makeFuture, trueRow, thresholdRow,\
    differenceRow
from psychsim.world import WORLD
from helpers import anding

class Victims:
    """ Methods for modeling victims within a psychsim self.world.

    Attributes:
        COLOR_REWARDS: How much reward for different color victims
        COLOR_REQD_TIMES: Number of seconds of triage required to save a victim
        COLOR_EXPIRY: Number of seconds until victim dies
        COLOR_PRIOR_P_P: Probability of a victim of a given color being present in a room
        COLOR_FOV_P: Probability that a player's FOV has a victim of a given color after a search action 
        
        STR_TRIAGE_ACT: String label for triage action
        STR_FOV_VAR: String label for the data field that indicates color of victim in FOV
        
        FULL_OBS: Observability of domain

        self.victimsByLocAndColor: A dict mapping a room to a dict mapping a color to the corresponding victim object
        
        self.triageActs: A map from a player to her triage actions
        self.searchActs: A map from a player to her search actions
        
        self.world: link to domain psychsim self.world

    """

    FULL_OBS = None

    COLORS = ['Green', 'Gold', 'Red', 'White']
    COLOR_REWARDS = {'Green':10, 'Gold':200}
    COLOR_REQD_TIMES = {'Green':1, 'Gold':1}
    COLOR_EXPIRY = {'Green':int(10*60), 'Gold':int(7*60)}
#    COLOR_EXPIRY = {'Green':15, 'Gold':7}
    COLOR_PRIOR_P = {'Green':0, 'Gold':0}
    COLOR_FOV_P = {'Green':0, 'Gold':0, 'Red':0, 'White':0}

    STR_TRIAGE_ACT = 'actTriage'
    STR_FOV_VAR = 'vicInFOV'
    
    def __init__(self):
    
        self.victimsByLocAndColor = {}
        
        self.triageActs = {}
        self.searchActs = {}
        self.world = None
        self.countSaved = False
    
    def makeVictims(self, vLocations, colors, humanNames, locationNames):
        """Method for creating victims in the self.world

        Parameters:
            vLocations: list of locations of victims
            colors: list containing the color of each victim
            humanNames: list of agent names that constitute legal values for the `savior` state of each victim
            locationNames: list of location names that constitute legal values for the `loc` state of each victim
        Returns:
            Creates victim agents, and adds them to the self.world. Adds each victim to `self.victimsByLocAndColor` dictionary.
        """
        assert(len(vLocations) == len(colors))
        self.numVictims = len(colors)
        self.vicNames = ['victim'+str(i) for i in range(self.numVictims)]
        for vi in range(self.numVictims):
            loc = vLocations[vi]
            color = colors[vi]
            self._makeVictim(vi, loc, color, humanNames, locationNames)
            
        ## Create location-centric counters for victims of each of the 2 colors
        victimClrCounts = {loc:{clr:0 for clr in Victims.COLOR_EXPIRY} for loc in locationNames}
        for loc,clr in zip(vLocations, colors):
            victimClrCounts[loc][clr] = victimClrCounts[loc][clr] + 1
            
        ## Create the psychsim version of these counters
        for loc in victimClrCounts.keys():
            for clr in victimClrCounts[loc].keys():
                ctr = self.world.defineState(WORLD, 'ctr_'+loc+'_'+clr, int)
                self.world.setFeature(ctr, victimClrCounts[loc][clr])


    def _makeVictim(self, vi, loc, color, humanNames, locationNames):
        victim = self.world.addAgent('victim' + str(vi))

        self.world.defineState(victim.name,'color',list,['Gold','Green','Red', 'White'])
        victim.setState('color',color)

        self.world.defineState(victim.name,'danger',float,description='How far victim is from health')
        victim.setState('danger', Victims.COLOR_REQD_TIMES[color])

        self.world.defineState(victim.name,'reward',int,description='Value earned by saving this victim')
        rew = Victims.COLOR_REWARDS[color]
        victim.setState('reward', rew)

        self.world.defineState(victim.name,'loc',list, locationNames)
        victim.setState('loc', loc)

        self.world.defineState(victim.name,'savior',list, ['none'] + humanNames, description='Name of agent who saved me, if any')
        victim.setState('savior', 'none')
                
        if loc not in self.victimsByLocAndColor.keys():
            self.victimsByLocAndColor[loc] = {}
        if color not in self.victimsByLocAndColor[loc].keys():
            self.victimsByLocAndColor[loc][color] = []
        self.victimsByLocAndColor[loc][color].append(victim)

    def setupTriager(self, VICTIMS_LOCS, VICTIM_TYPES, triageAgent, locations):
        ## Create counter of victims I saved of each color
        for color in Victims.COLOR_REQD_TIMES.keys():
            if self.countSaved:
                key = self.world.defineState(triageAgent.name, 'numsaved_' + color, int)
                self.world.setFeature(key, 0)
            else:
                key = self.world.defineState(triageAgent.name, 'numsaved_' + color, bool)
                self.world.setFeature(key, False)
            
        # create and initialize fov
        self.world.defineState(triageAgent.name,Victims.STR_FOV_VAR,list, ['none'] + Victims.COLORS)
        triageAgent.setState(Victims.STR_FOV_VAR,'none')

        self.makeVictims(VICTIMS_LOCS, VICTIM_TYPES, [triageAgent.name], locations)
        
        ## Create a triage action per victim color
        self.triageActs[triageAgent.name] = {}
        for color in Victims.COLOR_EXPIRY.keys():
            self.makeTriageAction(triageAgent, locations, color)
        
        self.makeVictimReward(triageAgent)
        return []

    def getUnObsName(loc,color):
        return 'unobs' + loc+'_'+color

    def createObsVars4Victims(self, human, allLocations):
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
                ks.append(self.world.defineState(human.name, Victims.getUnObsName(loc,color), bool))
                ds.append(Distribution({True:Victims.COLOR_PRIOR_P[color], False:1-Victims.COLOR_PRIOR_P[color]}))

        if Victims.FULL_OBS:
            for key in ks:
                self.world.setFeature(key, False)
        else:
            for i, (key,dist) in enumerate(zip(ks,ds)):
            	human.setBelief(key, dist)
            	self.world.setFeature(key, dist)

    def normalizeD(d, key):
        if len(d) == 1:
            return setToConstantMatrix(key, list(d.keys())[0])
        
        sammy = sum(d.values())
        nd = {c:p/sammy for c,p in d.items()}
        return {'distribution': [(setToConstantMatrix(key, c), p) for c,p in nd.items()]}

    def makeRandomFOVDistr(self, human, humanKey, allLocations):
        tree = {'if': equalRow(stateKey(human.name, 'loc'), allLocations)}
        for il, loc in enumerate(allLocations):
            if loc not in self.victimsByLocAndColor.keys():
                tree[il] = Victims.normalizeD({'none':1}, humanKey)
                continue
            
            [c1, c2,_,_] = Victims.COLORS
            allDistribs = {True:{True:Victims.normalizeD({c1:2, c2:2, 'none':1}, humanKey), 
                                 False:Victims.normalizeD({c1:2,'none':1}, humanKey)},
                           False:{True:Victims.normalizeD({c2:2, 'none':1}, humanKey), 
                                  False:Victims.normalizeD({'none':1}, humanKey)}}
            c1Counter = stateKey(WORLD, 'ctr_'+loc+'_'+c1)
            c2Counter = stateKey(WORLD, 'ctr_'+loc+'_'+c2)
            cond1 = thresholdRow(c1Counter, 0)
            cond2 = thresholdRow(c2Counter, 0)
            
            tree[il] = {'if':cond1,
                        True:  {'if': cond2, True: allDistribs[True][True],  False: allDistribs[True][False]},
                        False: {'if': cond2, True: allDistribs[False][True], False: allDistribs[False][False]}}
                        
        return tree
    
    def makeSearchAction(self, human, allLocations):
        action = human.addAction({'verb': 'search'})

        ## A victim can randomly appear in FOV
        fovKey  = stateKey(human.name, Victims.STR_FOV_VAR)
        fovTree = self.makeRandomFOVDistr(human, fovKey, allLocations)
        self.world.setDynamics(fovKey,action,makeTree(fovTree))

        ## For every location and victim color, if this color is in (future) FOV and player in loc,
        ## set the corresponding observed variable to True
        locKey = stateKey(human.name, 'loc')
        newFov = makeFuture(fovKey)
        for loc in allLocations:
            for color in ['Gold', 'Green']:
                obsVicColorKey = stateKey(human.name, Victims.getUnObsName(loc,color))
                if obsVicColorKey in self.world.variables:
                    tree = anding([equalRow(locKey, loc), equalRow(newFov, color)],
                                   setToConstantMatrix(obsVicColorKey, True),
                                   noChangeMatrix(obsVicColorKey))
                    self.world.setDynamics(obsVicColorKey,action,makeTree(tree))

        self.searchActs[human.name] = action
        
    def makeTriageAction(self, human, locations, color):
        fovKey = stateKey(human.name, Victims.STR_FOV_VAR)
        locKey = stateKey(human.name, 'loc')

        legal = {'if':equalRow(fovKey, color), True:True, False:False}
        action = human.addAction({'verb': 'triage_'+color}, makeTree(legal))
        
        self.setFOVToNewClr(human, action, 'White', locations, color)
        
        clock = stateKey(WORLD,'seconds')
        if color == 'Green':
            threshold = 7
        else:
            threshold = 14
        longEnough = differenceRow(makeFuture(clock), clock, threshold)
        
        for loc in self.victimsByLocAndColor.keys():
            if color not in self.victimsByLocAndColor[loc].keys():
                continue
            ## TODO: multiple 
            victim = self.victimsByLocAndColor[loc][color][0]
            vcolorKey = stateKey(victim.name,'color')
            saviorKey = stateKey(victim.name,'savior')
            
            ## Successful triage conditions
            conds = [equalRow(fovKey, color),
                     equalRow(locKey, loc),
                     longEnough]

            ## Color: if successful, victim turns white
            tree = makeTree(anding(conds,
                                   setToConstantMatrix(vcolorKey, 'White'),
                                   noChangeMatrix(vcolorKey)))
            self.world.setDynamics(vcolorKey,action,tree)
                            
            ## Savior:  if successful, set to human's name.
            tree = makeTree(anding(conds,
                                   setToConstantMatrix(saviorKey, human.name),
                                   noChangeMatrix(saviorKey)))
            self.world.setDynamics(saviorKey,action,tree)

            ## location-specific counter of vics of this color: if successful, decrement
            vicsInLocOfClrKey = stateKey(WORLD, 'ctr_'+loc+'_'+color)
            tree = makeTree(anding(conds,
                                   incrementMatrix(vicsInLocOfClrKey, -1),
                                   noChangeMatrix(vicsInLocOfClrKey)))
            self.world.setDynamics(vicsInLocOfClrKey,action, tree)  
            

        ## Color saved counter: if successful, increment
        self.makeSavedCtrDyn(human, action, color)
        self.triageActs[human.name][color] = action
        
    def setFOVToNewClr(self, human, action, newColor, locations, color):
        ''' Setting color of victim in FOV 
            For a color: If player colocated with victim of this color and victim's future = new color
            and FOV is this color, set FOV to new color
        '''
        humanLoc = stateKey(human.name, 'loc')
        fovKey = stateKey(human.name, Victims.STR_FOV_VAR)            
        ifTrue = setToConstantMatrix(fovKey, newColor)
        ifFalse = noChangeMatrix(fovKey)
        
        ## This tree has a branch per location
        mainTree = {'if':equalRow(humanLoc, locations)}
        for ic, loc in enumerate(locations):
            ## If location has no victims or none of this color, no change 
            if (loc not in self.victimsByLocAndColor.keys()) or (color not in self.victimsByLocAndColor[loc].keys()):
                mainTree[ic] = ifFalse
                continue
            
            ## TODO: multiple vics
            vic = self.victimsByLocAndColor[loc][color][0]
            mainTree[ic] = anding([equalRow(fovKey, color),
                            equalRow(makeFuture(stateKey(vic.name, 'color')), newColor)],
                            ifTrue,ifFalse)            
            
        self.world.setDynamics(fovKey, action, makeTree(mainTree))

    def makeSavedCtrDyn(self, human, action, color):
        ''' For each color, specify the dynamics for the flag that indicates whether
        player has just saved a victim of this color
        '''
        
        savedKey = stateKey(human.name, 'numsaved_'+color)
        ifTrue = setToConstantMatrix(savedKey, True)
        ifFalse = noChangeMatrix(savedKey)
        colorVics = []
        for vDict in self.victimsByLocAndColor.values():
            if color in vDict.keys():
                for v in vDict[color]:
                    colorVics.append(v)

        if len(colorVics) == 0:
            print('No vics of color', color)
            return
        thisAnd = anding([equalRow(stateKey(colorVics[0].name, 'savior'), 'none'),
                        equalRow(makeFuture(stateKey(colorVics[0].name, 'savior')), human.name)],
                        ifTrue, ifFalse)
        for vic in colorVics[1:]:
            thisAnd = anding([equalRow(stateKey(vic.name, 'savior'), 'none'),
                              equalRow(makeFuture(stateKey(vic.name, 'savior')), human.name)],
                             ifTrue,
                             thisAnd)

        tree = makeTree(thisAnd)
        print('made tree')
        self.world.setDynamics(savedKey,action, tree)
        print('did dynamics of saved ctr/flag')

#
#        ## Collect all victims of this color
#        colorVics = []
#        for vDict in self.victimsByLocAndColor.values():
#            if color in vDict.keys():
#                for v in vDict[color]:
#                    colorVics.append(v)
#
#        if len(colorVics) == 0:
#            print('No vics of this color in the world', color)
#            return
#        
#        savedKey = stateKey(human.name, 'numsaved_'+color)
#        if self.countSaved:
#            ifTrue = incrementMatrix(savedKey, 1)
#            ifFalse = noChangeMatrix(savedKey)
#        else:
#            ifTrue = setToConstantMatrix(savedKey, True)
#            ifFalse = noChangeMatrix(savedKey)
#            
#        thisAnd = anding([equalRow(stateKey(colorVics[0].name, 'savior'), 'none'),
#                        equalRow(makeFuture(stateKey(colorVics[0].name, 'savior')), human.name)],
#                        ifTrue, ifFalse)
#        for iv, vic in enumerate( colorVics[1:]):
#            thisAnd = anding([equalRow(stateKey(vic.name, 'savior'), 'none'),
#                              equalRow(makeFuture(stateKey(vic.name, 'savior')), human.name)],
#                             ifTrue,
#                             thisAnd)
#        tree = makeTree(thisAnd)
#        print('made tree')
#        self.world.setDynamics(savedKey,action, tree)
#        print('did dynamics of saved ctr/flag')

    def makeVictimReward(self, agent, model=None, rwd_dict=None):
        """ Human gets reward if flag is set
        """
#        rKey = rewardKey(agent.name)
#        rtree = nested_tree = {}
#        for color in Victims.COLOR_REQD_TIMES.keys():
#            rwd = rwd_dict[color] if rwd_dict is not None and color in rwd_dict else Victims.COLOR_REWARDS[color]
#            if len(nested_tree) > 0 and False not in nested_tree:
#                nested_tree[False] = {}
#                nested_tree = nested_tree[False]
#                
#            ## If number of saved victims of this color increased by 1
#            key = stateKey(agent.name, 'numsaved_' + color)
#            nested_tree['if'] = differenceRow(makeFuture(key), key, 1)
#            nested_tree[True] = setToConstantMatrix(rKey, rwd)
#
#        if len(rtree) > 0:
#            nested_tree[False] = noChangeMatrix(rKey)
#
#        agent.setReward(makeTree(rtree), 1., model)

    def getTriageAction(self, human, color):
        if type(human) == str:
            name = human
        else:
            name = human.name
        return self.triageActs[name][color]

    def getSearchAction(self, human):
        if type(human) == str:
            return self.searchActs[human]
        else:
            return self.searchActs[human.name]

    def triage(self, human, s, color):
        self.world.step(self.getTriageAction(human, color), select=s)

    def search(self, human, s):
        self.world.step(self.getSearchAction(human), select=s)
