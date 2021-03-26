import logging
import pathlib
import pandas as pd
from collections import OrderedDict
from atomic.definitions import Directions
from atomic.definitions import GOLD_STR, GREEN_STR

MAPS_DIR = (pathlib.Path(__file__).parent / '..' / '..' / 'maps').resolve()
SATURN_MAP_DIR = MAPS_DIR / 'Saturn'
FALCON_MAP_DIR = MAPS_DIR / 'Falcon_EMH_PsychSim'
FALCON_COORDS_FILE = str(MAPS_DIR / 'ASIST_FalconMap_Rooms_v1.1_EMH_OCN_VU-coords.csv')
FALCON_PORTALS_FILE = str(MAPS_DIR / 'ASIST_FalconMap_Portals_v1.1_EMH_OCN_VU.csv')
FALCON_ROOMS_FILE = str(MAPS_DIR / 'ASIST_FalconMap_Rooms_v1.1_EMH_OCN_VU.csv')


class MapData(object):
    def __init__(self, name, adjacency_file, room_file, victim_file, coords_file, portals_file, logger=logging):
        self.name = name
        self.adjacency_file = adjacency_file
        self.room_file = room_file
        self.victim_file = victim_file
        self.coords_file = coords_file
        self.portals_file = portals_file

        # gets map data from the different files
        self.adjacency = getSandRMap(fname=adjacency_file, logger=logger)
        self.rooms = set(self.adjacency.keys())
        self.rooms_list = list(self.rooms)
        self.victims = getSandRVictims(fname=victim_file)
        self.coordinates = getSandRCoords(fname=coords_file)
        self.init_loc = self.rooms_list[0]


def get_default_maps(logger=logging):
    return {
#        'sparky': MapData('sparky', str(MAPS_DIR / 'sparky_adjacency.csv'), None,
#                          str(MAPS_DIR / 'sparky_vic_locs.csv'),
#                          str(MAPS_DIR / 'sparky_coords.csv'), None, logger),
#        'falcon': MapData('falcon', str(MAPS_DIR / 'falcon_adjacency_v1.1_OCN.csv'), None,
#                          str(MAPS_DIR / 'falcon_vic_locs_v1.1_OCN.csv'),
#                          FALCON_COORDS_FILE, None, logger),
#        'FalconEasy': MapData('FalconEasy',
#                              str(FALCON_MAP_DIR / 'falcon_easy_adjacency.csv'), FALCON_ROOMS_FILE,
#                              str(FALCON_MAP_DIR / 'ASIST_FalconMap_Easy_Victims_v1.1_OCN_VU.csv'),
#                              FALCON_COORDS_FILE, FALCON_PORTALS_FILE, logger),
#        'FalconMed': MapData('FalconMed',
#                             str(FALCON_MAP_DIR / 'falcon_medium_adjacency.csv'), FALCON_ROOMS_FILE,
#                             str(FALCON_MAP_DIR / 'ASIST_FalconMap_Medium_Victims_v1.1_OCN_VU.csv'),
#                             FALCON_COORDS_FILE, FALCON_PORTALS_FILE, logger),
#        'FalconHard': MapData('FalconHard',
#                              str(FALCON_MAP_DIR / 'falcon_hard_adjacency.csv'), FALCON_ROOMS_FILE,
#                              str(FALCON_MAP_DIR / 'ASIST_FalconMap_Hard_Victims_v1.1_OCN_VU.csv'),
#                              FALCON_COORDS_FILE, FALCON_PORTALS_FILE, logger),
        'saturnA': MapData('saturnA',
                           str(SATURN_MAP_DIR / 'coordsNeighbs.csv'), 
                           str(SATURN_MAP_DIR / 'coordsNeighbs.csv'),
                           str(SATURN_MAP_DIR / 'saturnAPilotVictims.csv'), None, 
                           str(SATURN_MAP_DIR / 'saturn_doors.csv'), logger),   
        'saturnB': MapData('saturnB',
                           str(SATURN_MAP_DIR / 'coordsNeighbs.csv'), 
                           str(SATURN_MAP_DIR / 'coordsNeighbs.csv'),
                           str(SATURN_MAP_DIR / 'saturnBPilotVictims.csv'), None, 
                           str(SATURN_MAP_DIR / 'saturn_doors.csv'), logger),                           
#        'simple': MapData('simple',
#            str(MAPS_DIR / 'simple_adjacency.csv'), None, str(MAPS_DIR / 'simple_victims.csv'), None, None, logger),
    }


def checkSRMap(SRMap, logger=logging):
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


def getSandRMap(small=False, fname="sparky_adjacency", logger=logging):
    DN = Directions.N
    DS = Directions.S
    DE = Directions.E
    DW = Directions.W
    dirs = {"N": DN, "S": DS, "E": DE, "W": DW}

    if not fname.endswith(".csv"):
        fname = fname + ".csv"
    if small:
        fname = fname[:-4] + "_small.csv"
    conn_df = pd.read_csv(fname, sep=None, engine='python')
    toUpperCase = {c:c.upper() for c in conn_df.columns}
    conn_df.rename(toUpperCase, axis=1, inplace=True)
    print('-----------------', fname)
    num_col = len(conn_df.columns)
    SandRLocs = OrderedDict()
    for key, row in conn_df.iterrows():
        if row['ROOM'] not in SandRLocs.keys():
            SandRLocs[row["ROOM"]] = {}
        for i in range(num_col - 1):
            direction = conn_df.columns[i + 1]
            neighbor = row[direction]
            if type(neighbor) is str:
                SandRLocs[row["ROOM"]][dirs[direction]] = neighbor

    checkmap = checkSRMap(SandRLocs, logger)
    ## Bug here: checkSRMap always returns True!
    if checkmap:
        return SandRLocs
    else:
        logger.error("map contains errors")


def getSandRVictims(small=False, fname="sparky_vic_locs"):
    # Victims and triage actions
    if not fname.endswith(".csv"):
        fname = fname + ".csv"
    if small:
        fname = fname[:-4] + "_small.csv"
    vic_df = pd.read_csv(fname, sep=None, engine='python')
    SandRVics = {}
    for key, row in vic_df.iterrows():
        if "Victim Location" in vic_df.columns:
            col = "Victim Location"
            color = row["Color"]
        else:
            col = "RoomName"
            if row["FeatureType"].lower() == 'victim':
                color = GREEN_STR
            else:
                color = GOLD_STR
        if row[col] not in SandRVics.keys():
            SandRVics[row[col]] = []

        SandRVics[row[col]].append(color)       

    return SandRVics


def getSandRCoords(small=False, fname="sparky_coords"):
    if fname is None:
        return None
    if not fname.endswith(".csv"):
        fname = fname + ".csv"
    if small:
        fname = fname[:-4] + "_small.csv"
    coords = {}
    with open(fname, 'r') as f:
        lines = f.readlines()
        for line in lines:
            coord = line.split(',')
            coords[coord[0]] = float(coord[1]), float(coord[2])
    return coords
