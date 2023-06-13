import json
import os
from dataclasses import dataclass

from backend.breeding.axie_genome import *

AXIE_PARTS = ["eyes", "ears", "mouth", "horn", "back", "tail"]


AXIE_GENE_LEVELS = ["D", "R1", "R2"]
AXIE_STATS = {
    "Aquatic":  { "HP": 39, "Speed": 39, "Skill": 35, "Morale": 27 },
    "Beast":    { "HP": 31, "Speed": 35, "Skill": 31, "Morale": 43 },
    "Bird":     { "HP": 27, "Speed": 43, "Skill": 35, "Morale": 35 },
    "Bug":      { "HP": 35, "Speed": 31, "Skill": 35, "Morale": 39 },
    "Plant":    { "HP": 43, "Speed": 31, "Skill": 31, "Morale": 35 },
    "Reptile":  { "HP": 39, "Speed": 35, "Skill": 31, "Morale": 35 },
    "Dawn":     { "HP": 35, "Speed": 35, "Skill": 39, "Morale": 31 },
    "Dusk":     { "HP": 43, "Speed": 39, "Skill": 27, "Morale": 31 },
    "Mech":     { "HP": 31, "Speed": 39, "Skill": 43, "Morale": 27 }
}
AXIE_PART_STAT_BONUS = {
    "Aquatic":  { "HP": 1, "Speed": 3, "Skill": 0, "Morale": 0 },
    "Beast":    { "HP": 0, "Speed": 1, "Skill": 0, "Morale": 3 },
    "Bird":     { "HP": 0, "Speed": 3, "Skill": 0, "Morale": 1 },
    "Bug":      { "HP": 1, "Speed": 0, "Skill": 3, "Morale": 0 },
    "Plant":    { "HP": 3, "Speed": 0, "Skill": 0, "Morale": 1 },
    "Reptile":  { "HP": 3, "Speed": 1, "Skill": 0, "Morale": 0 },
}	

@dataclass(frozen=False)
class AxiePart:
    part_class: str
    part_name: str

@dataclass(frozen=False)
class AxieData:
    id: int
    name: str
    axie_class: str
    parts: dict
    image: str
    quality: float = 0

    priceUSD: float = None
    priceETH: float = None

    breedCount: int = 0
    sireId: list = None

    def getSpeed(self):
        speed = AXIE_STATS[self.axie_class]['Speed']
        for part in AXIE_PARTS:
            speed += AXIE_PART_STAT_BONUS[self.parts[part]['D'].part_class]['Speed']
        return speed

    def getHP(self):
        hp = AXIE_STATS[self.axie_class]['HP']
        for part in AXIE_PARTS:
            hp += AXIE_PART_STAT_BONUS[self.parts[part]['D'].part_class]['HP']
        return hp

    def getSkill(self):
        skill = AXIE_STATS[self.axie_class]['Skill']
        for part in AXIE_PARTS:
            skill += AXIE_PART_STAT_BONUS[self.parts[part]['D'].part_class]['Skill']
        return skill

    def getMorale(self):
        morale = AXIE_STATS[self.axie_class]['Morale']
        for part in AXIE_PARTS:
            morale += AXIE_PART_STAT_BONUS[self.parts[part]['D'].part_class]['Morale']
        return morale

    def __repr__(self):
        output_string = ""
        for part in AXIE_PARTS:
            for gene_level in AXIE_GENE_LEVELS:
                if part in ('eyes', 'ears'): output_string += self.parts[part][gene_level].part_class + "\t"
                else: output_string += self.parts[part][gene_level].part_name + "\t"
            output_string += "\n"
        return output_string


def createAxieData(traits: dict):
    axie_traits = parseGenes(traits['genes'])

    priceETH = 0
    priceUSD = 0
    try:
        priceETH = round(float(traits['auction.currentPrice']) / 1e18, 3)
        priceUSD = traits['auction.currentPriceUSD']
    except KeyError:
        pass

    return AxieData(
        id=traits['id'],
        name=traits['name'],
        axie_class=axie_traits['axie_class'],
        parts={
            part: {
                gene_level: 
                    AxiePart(
                        axie_traits[part][gene_level]['class'].capitalize(),
                        axie_traits[part][gene_level]['name'],
                    ) for gene_level in AXIE_GENE_LEVELS
            } for part in AXIE_PARTS
        },
        image=traits['image'],

        priceETH=priceETH,
        priceUSD=priceUSD,

        breedCount=traits['breedCount'],
        sireId=traits['sireId']
    )


def parseGenes(genes: str):
    '''
    Converts stringified hexadecimal axie genome to binary,
    then matches binary to the axie part library
    '''
    genesInt = int(genes, 16)
    genesStr = '{0:0256b}'.format(genesInt)
    return getTraits(genesStr)

def getTraits(genes):
    groups = [genes[0:32], genes[32:64], genes[64:96], genes[96:128], genes[128:160], genes[160:192], genes[192:224], genes[224:256]]

    axie_class = getClassFromGroup(groups[0]).capitalize()
    region = getRegionFromGroup(groups[0])

    eyes = getPartsFromGroup("eyes", groups[2], region)
    mouth = getPartsFromGroup("mouth", groups[3], region)
    ears = getPartsFromGroup("ears", groups[4], region)
    horn = getPartsFromGroup("horn", groups[5], region)
    back = getPartsFromGroup("back", groups[6], region)
    tail = getPartsFromGroup("tail", groups[7], region)
    return {'axie_class': axie_class, 'region': region, 'eyes': eyes, 'mouth': mouth, 'ears': ears, 'horn': horn, 'back': back, 'tail': tail}


def getClassFromGroup(group):
    bin = group[0:4]
    if bin not in CLASS_GENE_MAP:
        return "Unknown Class"
    return CLASS_GENE_MAP[bin]

REGION_GENE_MAP = {"00000": "global", "00001": "japan"}
def getRegionFromGroup(group):
    regionBin = group[8:13]
    if (regionBin in REGION_GENE_MAP):
        return REGION_GENE_MAP[regionBin]
    return "Unknown Region"

def getPartsFromGroup(part, group, region):
    skinBinary = group[0:2]
    is_mystic = skinBinary == "11"

    d_Class = CLASS_GENE_MAP[group[2:6]]
    d_Binary = group[6:12]
    d_Name = getPartName(d_Class, part, region, d_Binary, skinBinary)

    r1_Class = CLASS_GENE_MAP[group[12:16]]
    r1_Binary = group[16:22]
    r1_Name = getPartName(r1_Class, part, region, r1_Binary)

    r2_Class = CLASS_GENE_MAP[group[22:26]]
    r2_Binary = group[26:32]
    r2_Name = getPartName(r2_Class, part, region, r2_Binary)

    return {'D': getPartFromName(part, d_Name), 'R1': getPartFromName(part, r1_Name), 'R2': getPartFromName(part, r2_Name), 'is_mystic': is_mystic}

def getPartName(axie_class, part, region, binary, skinBinary="00"):
    trait = ""
    if binary in BINARY_TRAITS[axie_class][part]:
        if skinBinary == "11":
            trait = BINARY_TRAITS[axie_class][part][binary]["mystic"]
        elif skinBinary == "10":
            trait = BINARY_TRAITS[axie_class][part][binary]["xmas"]
        elif region in BINARY_TRAITS[axie_class][part][binary]:
            trait = BINARY_TRAITS[axie_class][part][binary][region]
        elif "global" in BINARY_TRAITS[axie_class][part][binary]:
            trait = BINARY_TRAITS[axie_class][part][binary]["global"]
        else:
            trait = "UNKNOWN Regional " + axie_class + " " + part
    else:
        trait = "UNKNOWN " + axie_class + " " + part
    return trait

def convertDictToPart(axie_trait):
    return AxiePart(part_class=axie_trait['class'].capitalize(), part_name=axie_trait['name'])

def getPartFromName(traitType, partName):
    traitId = traitType.lower() + "-" + partName.lower().replace(" ", "-").replace("?", "").replace(".", "").replace("'", "")
    bodyPartsMap = getBodyParts()
    return bodyPartsMap[traitId]

def getBodyParts():
    current_file_dir = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.abspath(current_file_dir + "/body-parts.json")) as f:
        bodyParts = json.load(f)

    bodyPartsMap = {}
    for part in bodyParts:
        bodyPartsMap[part['partId']] = part

    return bodyPartsMap
