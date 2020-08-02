from collections import OrderedDict
import logging
from new_locations import Directions
import os.path
import pandas as pd
from math import isnan

def checkSRMap(SRMap,logger=logging):
    # small verison of map for debugging
    DN = Directions.N
    DS = Directions.S
    DE = Directions.E
    DW = Directions.W
    inverseD = {DN:DS,DS:DN,DE:DW,DW:DE}

    for x in SRMap:
        #  input("press key to continue...")
        logger.debug("########## Checking room %s" % (x))
        #  print("room: ",x," neighbors: ", SRMap[x])
        for d in range(4):
            try:
                n = SRMap[x][d]
                #  print("direction: ",d, " neighbor: ",n)
            except:
                continue

            try:
                invd = inverseD[d]
                bn = SRMap[n][invd]
                #  print("room: ", n," neighbors: ", SRMap[n])
                #  print("direction ", invd, " neighbor: ",bn)
            except:
                logger.warning("%s has neighbor mismatch with %s" % (x,n))

    # return True if no errors
    logger.info("Check complete")
    return True

def getSandRMap(small=False,fldr="data",fname="sparky_adjacency",logger=logging):
    DN = Directions.N
    DS = Directions.S
    DE = Directions.E
    DW = Directions.W
    dirs = {"N":DN, "S":DS, "E":DE, "W":DW}

    if small:
        file = os.path.join(os.path.dirname(__file__),fldr,fname+"_small.csv")
    else:
        file = os.path.join(os.path.dirname(__file__),fldr,fname+".csv")
    conn_df = pd.read_csv(file,sep=None,engine='python')
    num_col = len(conn_df.columns)
    SandRLocs = OrderedDict()
    for key,row in conn_df.iterrows():
        if row['Room'] not in SandRLocs.keys():
            SandRLocs[row["Room"]] = {}
        for i in range(num_col-1):
            direction = conn_df.columns[i+1]
            neighbor = row[direction]
            if type(neighbor) is str:
                SandRLocs[row["Room"]][dirs[direction]] = neighbor

    logger.debug(SandRLocs)
    checkmap = checkSRMap(SandRLocs,logger)
    if checkmap:
        return SandRLocs
    else:
        logger.error("map contains errors")

def getSandRVictims(small=False,fldr="data",fname="sparky_vic_locs"):
    # Victims and triage actions
    if small:
        file = os.path.join(os.path.dirname(__file__),fldr,fname+"_small.csv")
    else:
        file = os.path.join(os.path.dirname(__file__),fldr,fname+".csv")
    vic_df = pd.read_csv(file,sep=None,engine='python')
    SandRVics = {}
    for key,row in vic_df.iterrows():
        if row['Victim Location'] not in SandRVics.keys():
            SandRVics[row["Victim Location"]] = []

        SandRVics[row["Victim Location"]].append(row["Color"])


    return SandRVics

def getSandRCoords():
    file = os.path.join(os.path.dirname(__file__), "data", "sparky_coords.csv")
    coords = {}
    with open(file, 'r') as f:
        lines = f.readlines()
        for line in lines:
            coord = line.split(',')
            coords[coord[0]] = float(coord[1]), float(coord[2])
    return coords