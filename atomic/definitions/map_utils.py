import logging
import os.path
import pandas as pd
from collections import OrderedDict
from atomic.definitions import Directions

FALCON_COORDS_FILE = 'ASIST_FalconMap_Rooms_v1.1_EMH_OCN_VU-coords'
mapDir = '../maps/Falcon_EMH_PsychSim/'

DEFAULT_MAPS = {'sparky': {'room_file': 'sparky_adjacency',
                           'victim_file': 'sparky_vic_locs',
                           'coords_file': 'sparky_coords'},
                'falcon': {'room_file': 'falcon_adjacency_v1.1_OCN',
                           'victim_file': 'falcon_vic_locs_v1.1_OCN',
                           'coords_file': FALCON_COORDS_FILE},
                'FalconEasy': {'room_file': mapDir + 'falcon_easy_adjacency',
                               'victim_file': mapDir + 'ASIST_FalconMap_Easy_Victims_v1.1_OCN_VU',
                               'coords_file': FALCON_COORDS_FILE},
                'FalconMed': {'room_file': 'falcon_medium_adjacency',
                              'victim_file': mapDir + 'ASIST_FalconMap_Medium_Victims_v1.1_OCN_VU',
                              'coords_file': FALCON_COORDS_FILE},
                'FalconHard': {'room_file': 'falcon_hard_adjacency',
                               'victim_file': mapDir + 'ASIST_FalconMap_Hard_Victims_v1.1_OCN_VU',
                               'coords_file': FALCON_COORDS_FILE},
                }


def checkSRMap(SRMap, logger=logging):
    # small verison of map for debugging
    DN = Directions.N
    DS = Directions.S
    DE = Directions.E
    DW = Directions.W
    inverseD = {DN: DS, DS: DN, DE: DW, DW: DE}

    for x in SRMap:
        #  input("press key to continue...")
#        logger.debug("########## Checking room %s" % (x))
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
                logger.warning("%s has neighbor mismatch with %s" % (x, n))

    # return True if no errors
    logger.info("Check complete")
    return True


def getSandRMap(small=False, fldr="../../maps", fname="sparky_adjacency", logger=logging):
    DN = Directions.N
    DS = Directions.S
    DE = Directions.E
    DW = Directions.W
    dirs = {"N": DN, "S": DS, "E": DE, "W": DW}

    if small:
        file = os.path.abspath(os.path.join(os.path.dirname(__file__), fldr, fname + "_small.csv"))
    else:
        file = os.path.abspath(os.path.join(os.path.dirname(__file__), fldr, fname + ".csv"))
    conn_df = pd.read_csv(file, sep=None, engine='python')
    print('-----------------', file)
    num_col = len(conn_df.columns)
    SandRLocs = OrderedDict()
    for key, row in conn_df.iterrows():
        if row['Room'] not in SandRLocs.keys():
            SandRLocs[row["Room"]] = {}
        for i in range(num_col - 1):
            direction = conn_df.columns[i + 1]
            neighbor = row[direction]
            if type(neighbor) is str:
                SandRLocs[row["Room"]][dirs[direction]] = neighbor
    
    checkmap = checkSRMap(SandRLocs, logger)
    ## Bug here: checkSRMap always returns True!
    if checkmap:
        return SandRLocs
    else:
        logger.error("map contains errors")


def getSandRVictims(small=False, fldr="../../maps", fname="sparky_vic_locs"):
    # Victims and triage actions
    if small:
        file = os.path.join(os.path.dirname(__file__), fldr, fname + "_small.csv")
    else:
        file = os.path.join(os.path.dirname(__file__), fldr, fname + ".csv")
    vic_df = pd.read_csv(file, sep=None, engine='python')
    SandRVics = {}
    for key, row in vic_df.iterrows():
        if row['Victim Location'] not in SandRVics.keys():
            SandRVics[row["Victim Location"]] = []

        SandRVics[row["Victim Location"]].append(row["Color"])

    return SandRVics


def getSandRCoords(small=False, fldr="../../maps", fname="sparky_coords"):
    if fname is None:
        return None
    if small:
        file = os.path.join(os.path.dirname(__file__), fldr, fname + "_small.csv")
    else:
        file = os.path.join(os.path.dirname(__file__), fldr, fname + ".csv")
    coords = {}
    with open(file, 'r') as f:
        lines = f.readlines()
        for line in lines:
            coord = line.split(',')
            coords[coord[0]] = float(coord[1]), float(coord[2])
    return coords
