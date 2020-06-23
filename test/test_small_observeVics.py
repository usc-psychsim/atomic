# -*- coding: utf-8 -*-
"""
Created on Wed Feb 19 14:35:40 2020

@author: mostafh
"""
from psychsim.world import World
from psychsim.pwl import stateKey, modelKey, Distribution
from new_locations_fewacts import Locations, Directions
from victims_clr import Victims

if True:
    # MDP or POMDP
    Victims.FULL_OBS = False

    world = World()
    triageAgent = world.addAgent('TriageAg1')
    agent = world.addAgent('ATOMIC')
    Victims.world = world
    Locations.world = world
    
    VICTIMS_LOCS = ['E1']
    VICTIM_TYPES = ['Green']
    Victims.COLOR_PRIOR_P = {'Green':0.3, 'Gold':0.4}
    # if the following prob's add up to 1, FOV will never be empty after a search
    Victims.COLOR_FOV_P = {'Green':0.2, 'Gold':0.2, 'Red':0.2, 'White':0.4}
    
    Victims.makeVictims(VICTIMS_LOCS, VICTIM_TYPES, [triageAgent.name], ['E1'])
    Victims.makePreTriageActions(triageAgent)
    Victims.makeTriageAction(triageAgent)

    ################# Locations and Move actions
    Locations.makeMapDict({'BH1':{Directions.E:'E1'},
                           'E1' :{Directions.W:'BH1'}})
    
    Locations.makePlayerLocation(triageAgent, Victims, "E1")
    Locations.AllLocations = list(Locations.AllLocations)
    
	## These must come before setting triager's beliefs
    world.setOrder([{triageAgent.name}])

    Victims.createObsVars4Victims(triageAgent, ['E1'])
    Victims.makeSearchAction(triageAgent, ['E1'])
    
    triageAgent.resetBelief()
    triageAgent.omega = [key for key in world.state.keys() if key not in \
                   {modelKey(agent.name)}]

    world.save('obs.psy')
    

    def runit(events):
        for (msg, es, selectFlg) in events:
            for e in es:
                if type(e) == list:
                    world.setFeature(e[0], e[1])
                else:
                    world.step(e, select=selectFlg)
            print('== state after', msg)
            world.printState(beliefs=False)
            print('== T''s belief after', msg)
            world.printBeliefs(triageAgent.name)
        
    entries = [('before anyting', [], None),
               ('searching once', [Victims.searchActs[triageAgent.name]], True),
               ('victim is rescued', [[stateKey('victim0', 'color'), 'White'],
                                      [stateKey('victim0', 'savior'), 'TriageAg1']], None),
               ]
    
    suxTrig = [('before anyting', [], None),
               ('searching once', [Victims.searchActs[triageAgent.name]], True),
               ('approach and put in CH', [Victims.approachActs[triageAgent.name],
                                           Victims.crosshairActs[triageAgent.name],], True),
                ('triage', [Victims.triageActs[triageAgent.name]], True)    
               ]
    
    
    srch= [('searching after white', [Victims.searchActs[triageAgent.name]], True)]

    ## This runs fine
    runit(entries)

    ## This breaks
#    runit(entries + srch)
             
    ## This breaks
#    runit([entries[0], entries[2], srch[0]])
    
    ## This runs fine
#    runit(suxTrig)
    
    ## This runs fine          
#    runit(suxTrig + srch)
    
#
#    triageAgent.updateBeliefs(world.state, [])
#    
    
    
    
    
#    print('before anyting') 
#    world.printState(beliefs=False) 
#     
#    world.step(Victims.searchActs[triageAgent.name], select=True) 
#    print('=== after searching once') 
#    world.printState(beliefs=False) 
#    print('== T''s belief after searching once')
#    world.printBeliefs(triageAgent.name, False)
#     
#    world.setFeature(stateKey('victim0', 'color'), 'White') 
#    world.step(Victims.searchActs[triageAgent.name])     
#    print('=== after the victim is rescued') 
#    world.printState(beliefs=False) 
#    print('== T''s belief after victim is rescued')
#    world.printBeliefs(triageAgent.name, False)
#         