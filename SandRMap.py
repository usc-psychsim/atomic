from new_locations import Directions
import pandas as pd
from math import isnan

def checkSRMap(SRMap):
    # small verison of map for debugging
    DN = Directions.N
    DS = Directions.S
    DE = Directions.E
    DW = Directions.W
    inverseD = {DN:DS,DS:DN,DE:DW,DW:DE}

    for x in SRMap:
        #  input("press key to continue...")
        print("########## Checking room ", x)
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
                print("neighbor mismatch with ", n)

    # return True if no errors
    print("Check complete")
    return True

def getSmallSandRMap():
    # small verison of map for debugging
    DN = Directions.N
    DS = Directions.S
    DE = Directions.E
    DW = Directions.W

    SandRLocs = {"BH1":{DS:"BH2",DE:"E1",DW:"MR"}, "BH2":{DN:"BH1",DE:"E2",DW:"WR"},\
            "MR":{DE:"BH1",DW:"MR0"}, "MR0":{DE:"MR"},"WR":{DE:"BH2"}, "WR1":{DE:"WR"},\
            "E1":{DW:"BH1"}, "E2":{DW:"BH2"}}

    SandRLocs_small = {k: SandRLocs[k] for k in SandRLocs.keys() & {"BH1","BH2","MR","MR0","WR","WR1","E1","E2"}}

    print(SandRLocs_small)

    return SandRLocs_small

def getSandRMap(small=False):
    DN = Directions.N
    DS = Directions.S
    DE = Directions.E
    DW = Directions.W
    dirs = {"N":DN, "S":DS, "E":DE, "W":DW}

    if small:
        file = "data/sparky_adjacency_small.csv"
    else:
        file = "data/sparky_adjacency.csv"
    conn_df = pd.read_csv(file,sep=None)
    num_col = len(conn_df.columns)
    SandRLocs = {}
    for key,row in conn_df.iterrows():
        if row['Room'] not in SandRLocs.keys():
            SandRLocs[row["Room"]] = {}
        for i in range(num_col-1):
            direction = conn_df.columns[i+1]
            neighbor = row[direction]
            if type(neighbor) is str:
                SandRLocs[row["Room"]][dirs[direction]] = neighbor

    print(SandRLocs)
    checkmap = checkSRMap(SandRLocs)
    if checkmap:
        return SandRLocs
    else:
        print("map contains errors")

def getSandRVictims(small=False):
    # Victims and triage actions
    if small:
        file = "data/sparky_vic_locs_small.csv"
    else:
        file = "data/sparky_vic_locs.csv"
    vic_df = pd.read_csv(file,sep=None,engine='python')
    SandRVics = {}
    for key,row in vic_df.iterrows():
        if row['Victim Location'] not in SandRVics.keys():
            SandRVics[row["Victim Location"]] = []

        SandRVics[row["Victim Location"]].append(row["Color"])


    return SandRVics

def getSmallSandRVictims():
    # small version of victims for debugging
    G = "Green"
    O = "Gold"
    SandRVics = {"MR":O, "WR":G, "E1":G, "E2":O}
    return SandRVics

getSmallSandRMap()
