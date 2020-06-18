# -*- coding: utf-8 -*-
"""
Created on Wed Feb 19 14:35:40 2020

@author: mostafh
"""
from psychsim.world import World
from psychsim.pwl import stateKey, actionKey, modelKey, Distribution

def test():
	world = World()

	testAgent = world.addAgent('tester')
	action = testAgent.addAction({'verb': 'tact'})
	world.setOrder([{testAgent.name}])
	
	k1 = world.defineState(testAgent.name, 'k1', bool)
	k2 = world.defineState(testAgent.name, 'k2', bool)
	d1 = Distribution({True:.2, False:.8})
	d2 = Distribution({True:.3, False:.7})
	testAgent.setBelief(k1,d1)
	testAgent.setBelief(k2,d2)
	
	world.setFeature(k1,d1)
	world.setFeature(k2,d2)
	world.printBeliefs(testAgent.name)
    
	world.step(action)

if __name__ == '__main__':
	test()
    
    
