from new_locations import Directions

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
                raise("mismatched neighbors")

    # return True if no errors
    return True


def getSmallSandRMap():
    # small verison of map for debugging
    DN = Directions.N
    DS = Directions.S
    DE = Directions.E
    DW = Directions.W

    SandRLocs = {"BH1":{DS:"BH2",DE:"E1",DW:"MR"}, "BH2":{DN:"BH1",DE:"E2",DW:"WR"}, "MR":{DE:"BH1"},\
            "WR":{DE:"BH2"}, "E1":{DW:"BH1"}, "E2":{DW:"BH2"}}

    checkmap = checkSRMap(SandRLocs)
    if checkmap:
        return SandRLocs
    else:
        print("map contains errors")

def getSandRMap():
    DN = Directions.N
    DS = Directions.S
    DE = Directions.E
    DW = Directions.W

    SandRLocs = {"LH1":{DN:"LH2",DE:"XHL2"},"LH2":{DN:"LH3",DS:"LH1",DE:"203"},"LH3":{DS:"LH2",DE:"205"},\
            "XHL2":{DN:"201",DE:"XHL1",DW:"LH1"},"XHL1":{DN:"RJ",DE:"XHC",DW:"XHL2"},"XHC":{DN:"CH1",\
            DS:"BH1",DE:"XHR",DW:"XHL1"},"XHR":{DN:"RH1",DW:"XHC"},\
            "CH1":{DN:"CH2",DS:"XHC",DE:"209"},"CH2":{DN:"CH3",DS:"CH1",DE:"211",DW:"208S"},\
            "CH3":{DN:"CH4",DS:"CH2",DW:"208N"},"CH4":{DS:"CH3",DE:"215",DW:"210"},\
            "RH1":{DN:"RH2",DS:"XHR",DW:"216S"},"RH2":{DN:"RH3",DS:"RH1",DW:"216N"},\
            "RH3":{DN:"RH4",DS:"RH2",DW:"218"},"RH4":{DS:"RH3",DW:"220"},\
            "BH1":{DN:"XHC",DS:"BH2",DE:"E1",DW:"MR"},"BH2":{DN:"BH1",DE:"E2",DW:"WR"},"MR":{DE:"BH1"},\
            "WR":{DE:"BH2"},"E1":{DW:"BH1"},"E2":{DW:"BH2"},"201":{DN:"203",DS:"XHL2"},\
            "203":{DS:"201",DE:"208S",DW:"LH2"},"205":{DN:"207",DW:"LH3"},"207":{DS:"205",DE:"210"},\
            "210":{DE:"CH4",DW:"207"},"208N":{DS:"208S",DE:"CH3"},"208S":{DN:"208N",DE:"CH3",DW:"203"},\
            "RJ":{DS:"XHL1"},"209":{DE:"216S",DW:"CH1"},"211":{DN:"213",DW:"CH2"},\
            "213":{DS:"211",DE:"218"},"215":{DE:"220",DW:"CH4"},"220":{DE:"RH4",DW:"215"},\
            "218":{DE:"RH3",DW:"213"},"216N":{DS:"216S",DE:"RH2"},\
            "216S":{DN:"216N",DE:"RH1",DW:"209"}}

    checkmap = checkSRMap(SandRLocs)
    if checkmap:
        return SandRLocs
    else:
        print("map contains errors")

def getSandRVictims():
################# Victims and triage actions
## One entry per victim
# using 4 victim types. For now only 1 victim will be considered for each area. If there
# are more than 1 the one with the highest number (as encoded below) will be used in this model
# 0. mild/moderate: corresponds to Blue/Green/Yellow in the S&R .svg map
# 1. serious: corresponds to Orange/Red in the .svg
# 2. mild/moderate: 2-person victim
# 3. serious: 2-person victim
    SandRVics = {"LH3":2, "MR":1, "WR":0, "E1":0, "E2":1, "201":1, "203":0, "205":1, "207":1,\
                "210":0, "208N":0, "RJ":0, "209":1, "211":1, "213":1, "215":0, "220":1, "218":2,\
                "216N":0, "216S":1}
    return SandRVics

def getSmallSandRVictims():
    # small version of victims for debugging
    SandRVics = {"MR":1, "WR":0, "E1":0, "E2":1}
    return SandRVics
