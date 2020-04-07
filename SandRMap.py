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
    print("Check complete")
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

    SandRLocs = {"LH1":{DN:"LH2",DE:"XHL2"},"LH2":{DN:"LH3",DS:"LH1",DE:"R203"},"LH3":{DS:"LH2",DE:"R205"},\
            "XHL2":{DN:"R201",DE:"XHL1",DW:"LH1"},"XHL1":{DN:"RJ",DE:"XHC",DW:"XHL2"},"XHC":{DN:"CH1",\
            DS:"BH1",DE:"XHR",DW:"XHL1"},"XHR":{DN:"RH1",DW:"XHC"},\
            "CH1":{DN:"CH2",DS:"XHC",DE:"R209"},"CH2":{DN:"CH3",DS:"CH1",DE:"R211",DW:"R208S"},\
            "CH3":{DN:"CH4",DS:"CH2",DW:"R208N"},"CH4":{DS:"CH3",DE:"R215",DW:"R210"},\
            "RH1":{DN:"RH2",DS:"XHR",DW:"R216S"},"RH2":{DN:"RH3",DS:"RH1",DW:"R216N"},\
            "RH3":{DN:"RH4",DS:"RH2",DW:"R218"},"RH4":{DS:"RH3",DW:"R220"},\
            "BH1":{DN:"XHC",DS:"BH2",DE:"E1",DW:"MR"},"BH2":{DN:"BH1",DE:"E2",DW:"WR"},"MR":{DE:"BH1"},\
            "WR":{DE:"BH2"},"E1":{DW:"BH1"},"E2":{DW:"BH2"},"R201":{DN:"R203",DS:"XHL2"},\
            "R203":{DS:"R201",DE:"R208S",DW:"LH2"},"R205":{DN:"R207",DW:"LH3"},"R207":{DS:"R205",DE:"R210"},\
            "R210":{DE:"CH4",DW:"R207"},"R208N":{DS:"R208S",DE:"CH3"},"R208S":{DN:"R208N",DE:"CH3",DW:"R203"},\
            "RJ":{DS:"XHL1"},"R209":{DE:"R216S",DW:"CH1"},"R211":{DN:"R213",DW:"CH2"},\
            "R213":{DS:"R211",DE:"R218"},"R215":{DE:"R220",DW:"CH4"},"R220":{DE:"RH4",DW:"R215"},\
            "R218":{DE:"RH3",DW:"R213"},"R216N":{DS:"R216S",DE:"RH2"},\
            "R216S":{DN:"R216N",DE:"RH1",DW:"R209"}}

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
    SandRVics = {"LH3":2, "MR":1, "WR":0, "E1":0, "E2":1, "R201":1, "R203":0, "R205":1, "R207":1,\
                "R210":0, "R208N":0, "RJ":0, "R209":1, "R211":1, "R213":1, "R215":0, "R220":1, "R218":2,\
                "R216N":0, "R216S":1}
    return SandRVics

def getSmallSandRVictims():
    # small version of victims for debugging
    SandRVics = {"MR":1, "WR":0, "E1":0, "E2":1}
    return SandRVics
