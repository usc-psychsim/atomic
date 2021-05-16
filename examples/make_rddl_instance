#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat May 15 17:27:09 2021

@author: mostafh
"""



from atomic.parsing.map_parser import generate_rddl_str

def make_rddl_inst(map_file =       '../maps/Saturn/Saturn_1.4_3D_sm_v1.0.json',
                   rddl_template =  '../data/rddl_psim/sar_v3_template.rddl',
                   rddl_out =       '../data/rddl_psim/sar_v3_inst1.rddl'):
    ''' Create a RDDL instance from a RDDL template containing everything but the locations and adjacency info 
        which are obtained from a semantic map.
    '''

    loc_str, nbr_str = generate_rddl_str(map_file)
    
    rddl_temp_file = open(rddl_template, "r")
    
    rddl_str = rddl_temp_file.read()
    rddl_str = rddl_str.replace('LOCSTR', loc_str).replace('NBRSTR', nbr_str)
    
    rddl_inst_file = open(rddl_out, "w")
    rddl_inst_file.write(rddl_str)
    
    rddl_temp_file.close()
    rddl_inst_file.close()