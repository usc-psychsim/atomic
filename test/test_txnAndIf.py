# -*- coding: utf-8 -*-
"""
Created on Wed Feb 19 14:35:40 2020

@author: mostafh
"""
from psychsim.world import World
from psychsim.pwl import Distribution, equalFeatureRow, makeTree,  setToConstantMatrix, makeFuture, equalRow

def test():
	world = World()

	testAgent = world.addAgent('tester')
	action = testAgent.addAction({'verb': 'tact'})
	world.setOrder([{testAgent.name}])
	
	subjVar = world.defineState(testAgent.name, 'subjVar', bool)
	world.setFeature(subjVar,True)

	fov = world.defineState(testAgent.name, 'fov', list, ['a','b'])
	world.setFeature(fov,'a')

	fovtree = makeTree({'distribution': [(setToConstantMatrix(fov, 'a'), 0.09),
                                         (setToConstantMatrix(fov, 'b'), 0.91)]})
	world.setDynamics(fov, action, fovtree)
    
	subjtree = makeTree({'if':equalRow(makeFuture(fov), 'a'),
                         True:setToConstantMatrix(subjVar, True),
                         False: setToConstantMatrix(subjVar, False)
                         })
	world.setDynamics(subjVar, action, subjtree )

	world.printState()    
	world.step(action, select=True)
	print('after')
	world.printState()

if __name__ == '__main__':
	test()
    
    
