# #!/usr/bin/env python3
# # -*- coding: utf-8 -*-
# """
# Created on Sat Jun 20 15:39:15 2020
#
# @author: mostafh
# """
# import logging
#
# from psychsim.world import World, WORLD
# from psychsim.pwl import makeTree, incrementMatrix, modelKey, rewardKey
# from locations_no_pre import Locations
# from multivic import Victims
# from psychsim.pwl import modelKey, rewardKey
# from ftime import makeExpiryDynamics, incrementTime, stochasticTriageDur, PHASE_FEATURE, MISSION_PHASES, START_STR
# import atomic
#
#
# def makeWorld(playerName, initLoc, SandRLocs, SandRVics, use_unobserved=True, full_obs=False, logger=logging):
#     world = World()
#     time = world.defineState(WORLD, 'seconds', int, description='The mission clock time')
#     world.setFeature(time, 0)
#
#     phase_feat = world.defineState(WORLD, PHASE_FEATURE, list, MISSION_PHASES, description='The mission phase')
#     world.setFeature(phase_feat, START_STR)
#
#     triageAgent = world.addAgent(playerName)
#
#     ################# Victims and triage actions
#     victimsObj = Victims()
#     victimsObj.FULL_OBS = full_obs
#     victimsObj.COLOR_PRIOR_P = {'Green': 0.3, 'Gold': 0.4}
#     # if the following prob's add up to 1, FOV will never be empty after a search
#     victimsObj.COLOR_FOV_P = {'Green': 0.2, 'Gold': 0.2, 'Red': 0.2, 'White': 0.4}
#
#     victimsObj.world = world
#     VICTIMS_LOCS = []
#     VICTIM_TYPES = []
#     for loc, vics in SandRVics.items():
#         for vic in vics:
#             if loc.startswith('2'):
#                 loc = 'R' + loc
#             VICTIMS_LOCS.append(loc)
#             VICTIM_TYPES.append(vic)
#     victimsObj.setupTriager(VICTIMS_LOCS, VICTIM_TYPES, triageAgent, list(SandRLocs.keys()))
#
#     ################# Locations and Move actions
#     Locations.EXPLORE_BONUS = 0
#     Locations.world = world
#     Locations.makeMapDict(SandRLocs)
#     Locations.makePlayerLocation(triageAgent, initLoc)
#     Locations.AllLocations = list(Locations.AllLocations)
#     logger.debug('Made move actions')
#
#
#     ### Triage action (has to come after FOV and locations)
#     victimsObj.createTriageActions(triageAgent, list(SandRLocs.keys()))
#
#     ################# T I M E
#     ## Increment time by default
#     incrementTime(world)
#
#     ## Make victim expiration dynamics
#     makeExpiryDynamics([triageAgent.name], list(SandRLocs.keys()), world, victimsObj.COLOR_EXPIRY)
#     # ## Reflect victims turning to red on player's FOV
#     # victimsObj.setFOVToNewClr(triageAgent, True, 'Red', Locations.AllLocations, 'Gold')
#     # victimsObj.setFOVToNewClr(triageAgent, True, 'Red', Locations.AllLocations, 'Green')
#
#     ## Create stochastic duration for triage actions
#     triageDurationDistr = {}
#     triageDurationDistr['Gold'] = {5: 0.2, 15: 0.4}
#     triageDurationDistr['Green'] = {5: 0.2, 8: 0.4}
#     for color, durs in triageDurationDistr.items():
#         stochasticTriageDur(victimsObj, durs, world, color)
#
#
#     ## These must come before setting triager's beliefs
#     world.setOrder([{triageAgent.name}])
#
#     agent = atomic.make_observer(world, [triageAgent.name], 'ATOMIC')
#
#     if not victimsObj.FULL_OBS:
#         if use_unobserved:
#             logger.debug('Start to make observable variables and priors')
#             victimsObj.createObsVars4Victims(triageAgent, Locations.AllLocations)
#         logger.debug('Made observable variables and priors')
#     victimsObj.makeSearchAction(triageAgent, Locations.AllLocations)
#     logger.debug('Made search action')
#
#     triageAgent.resetBelief()
#     triageAgent.omega = [key for key in world.state.keys()
#                          if not ((key in {modelKey(agent.name), rewardKey(triageAgent.name)})
#                                  or key.startswith('victim')
#                                  or (key.find('unobs') > -1))]
#
#     return world, triageAgent, agent, victimsObj
