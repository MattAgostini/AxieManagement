import pandas as pd

from backend.queryMarketplace import MarketplaceSearchCriteria
from backend.parse_axie import AXIE_GENE_LEVELS, AxieData, AXIE_PARTS, AxiePart
from backend.breeding.axie_genome import *

def evaluateAxieQuality(axie: AxieData, query: MarketplaceSearchCriteria):
    ''' Axie Quality: A score value, starting at 100, decreasing by the likelihood of each undireable trait '''
    
    acceptablePartDict = {}
    acceptablePartDict['eyes'] = query.eyes
    acceptablePartDict['ears'] = query.ears
    acceptablePartDict['mouth'] = [mouth['name'] for mouth in query.mouth]
    acceptablePartDict['horn'] = [horn['name'] for horn in query.horn]
    acceptablePartDict['back'] = [back['name'] for back in query.back]
    acceptablePartDict['tail'] = [tail['name'] for tail in query.tail]

    quality = 1.0
    for part in AXIE_PARTS:
        axie_part = axie.parts[part]
        for gene_level in AXIE_GENE_LEVELS:
            if part in ['eyes', 'ears']:
                if axie_part[gene_level].part_class not in acceptablePartDict[part]: quality -= PROBABILITIES[gene_level]
            else:
                if axie_part[gene_level].part_name not in acceptablePartDict[part]: quality -= PROBABILITIES[gene_level]
    return round(quality * 100, 2)

def calculateOutcomes(parents: list, critical_stat: str):
    ''' 
    Given two axies, computes the various mating outcomes and their likelihood.
    The only things we care about are the 4 axie card (mouth, horn, back, tail) parts
    and the axie stats, which are determined by the class, and ALL D traits
    '''

    if parents[0].sireId == parents[1].sireId: # TODO: Have to check matron (do outer product to be sure) as well 
        return None

    qualityOutcome = min(parents[0].quality, parents[1].quality)
    classOutcomes = computeClassOutcome(parents)
    coalesceProbabilities(parents, critical_stat)

    # Computing part outcomes based on genes
    part_outcomes = {}
    for part in AXIE_PARTS:
        part_outcomes[part] = {}
        for parent in parents:
            part_data = parent.parts[part]
            for gene_level in AXIE_GENE_LEVELS:
                if part in ('eyes', 'ears'):
                    part_outcomes[part][part_data[gene_level].part_class] = part_outcomes[part].get(part_data[gene_level].part_class, 0) + PROBABILITIES[gene_level]
                else:
                    combined_name = f'{part_data[gene_level].part_class}-{part_data[gene_level].part_name}'
                    part_outcomes[part][combined_name] = part_outcomes[part].get(combined_name, 0) + PROBABILITIES[gene_level]
        part_outcomes[part] = dict(sorted(part_outcomes[part].items(), key=lambda item: item[1], reverse=True))

    outcomes = {}
    for eyes in part_outcomes['eyes']:
        for ears in part_outcomes['ears']:
            for mouth in part_outcomes['mouth']:
                for horn in part_outcomes['horn']:
                    for back in part_outcomes['back']:
                        for tail in part_outcomes['tail']:
                            outcomes_str = eyes + "  " + ears + "  " + mouth + "  " + horn + "  " + back + "  " + tail
                            outcome = (part_outcomes['eyes'][eyes] * part_outcomes['ears'][ears] *  part_outcomes['mouth'][mouth] * part_outcomes['horn'][horn] * part_outcomes['back'][back] *  part_outcomes['tail'][tail])
                            outcomes[outcomes_str] = outcome

    outcomes = dict(sorted(outcomes.items(), key=lambda item: item[1], reverse=True)[:4])

    axie_outcomes = []
    for outcome in outcomes:
        axie_outcomes.append((convertOutcomeToAxie(outcome, classOutcomes, qualityOutcome), outcomes[outcome]))
    return axie_outcomes


def convertOutcomeToAxie(outcome, classOutcomes, qualityOutcome):
    parts = outcome.split("  ")

    axie_parts = []
    for i, part in enumerate(AXIE_PARTS):
        if part in ['eyes', 'ears']:
            axie_parts.append(AxiePart(parts[i], ""))
        else:
            axie_parts.append(AxiePart(parts[i].split('-')[0], parts[i].split('-')[1]))

    return AxieData(
        id=0,
        axie_class="Bird", # FIXME: Use actual class
        parts={
            part: {
                gene_level: axie_parts[i] for gene_level in AXIE_GENE_LEVELS
            } for i, part in enumerate(AXIE_PARTS)
        },
        quality=qualityOutcome
    )


def convertAxieToMarketplaceQuery(axie: AxieData, critical_stat: str):
    axie_mouth = 'mouth-' + axie.parts['mouth']['D'].part_name.lower().replace(" ", "-")
    axie_horn =  'horn-'  + axie.parts['horn']['D'].part_name.lower().replace(" ", "-")
    axie_back =  'back-'  + axie.parts['back']['D'].part_name.lower().replace(" ", "-")
    axie_tail =  'tail-'  + axie.parts['tail']['D'].part_name.lower().replace(" ", "-")
    axie_parts = [axie_mouth, axie_horn, axie_back, axie_tail]

    hp = axie.getHP() if critical_stat == "HP" else 0
    speed = axie.getSpeed() if critical_stat == "Speed" else 0

    return MarketplaceSearchCriteria(classes=[axie.axie_class],
                                              parts=axie_parts,
                                              breedCount=[0, 0],
                                              hp=[hp, 61],
                                              speed=[speed, 61])
    


def coalesceProbabilities(parents: list, critical_stat: str):
    ''' This function combines probabilities of axie breeding results across a specified stat axis '''
    for parent in parents:
        for part in AXIE_PARTS:
            if part not in ['eyes', 'ears']: continue
            for gene_level in AXIE_GENE_LEVELS:
                if critical_stat == "Speed":
                    if parent.parts[part][gene_level].part_class == "Aquatic": parent.parts[part][gene_level].part_class = parent.axie_class
                    if parent.parts[part][gene_level].part_class == "Bird": parent.parts[part][gene_level].part_class = parent.axie_class
                if critical_stat == "HP":
                    if parent.parts[part][gene_level].part_class == "Plant": parent.parts[part][gene_level].part_class = parent.axie_class
                    if parent.parts[part][gene_level].part_class == "Reptile": parent.parts[part][gene_level].part_class = parent.axie_class

def computeClassOutcome(parents: list):
    classOutcomes = {}
    for parent in parents:
        classOutcomes[parent.axie_class] = classOutcomes.get(parent.axie_class, 0) + 0.5
    return classOutcomes


MAX_BREEDS = 7
def computeBreedCount(expectedOutcomeValue: float, SPL_conversion: float, AXS_conversion: float):
    breedCount = 0
    for i in range(MAX_BREEDS):
        if getMarginalBreedingCost(i, SPL_conversion, AXS_conversion) > expectedOutcomeValue: break
        breedCount = breedCount + 1
    return breedCount

SLP_BREEDING_COST = [600, 900, 1500, 2400, 3900, 6300, 10200]
AXS_BREEDING_COST = [1,   1,   1,    1,    1,    1,    1]
def getMarginalBreedingCost(start: int, SPL_conversion: float, AXS_conversion: float):
    return (SLP_BREEDING_COST[start] * SPL_conversion) + (AXS_BREEDING_COST[start] * AXS_conversion)

# This currently assumes we are starting at 0 breeds
def getTotalBreedingCost(breeds: int, SPL_conversion: float, AXS_conversion: float):
    total_SLP = 0
    total_AXS = 0
    for i in range(breeds):
        total_SLP = total_SLP + SLP_BREEDING_COST[i]
        total_AXS = total_AXS + AXS_BREEDING_COST[i]
    return (total_SLP * SPL_conversion) + (total_AXS * AXS_conversion)

def selectOptimalPairs(pair_dataframe):
    final_dataframe = pd.DataFrame(columns=pair_dataframe.columns)
    while len(pair_dataframe) > 0:
        best_result = pair_dataframe.loc[pair_dataframe['return_on_investment'].idxmax()]
        final_dataframe.loc[-1] = best_result
        final_dataframe.index = final_dataframe.index + 1
        final_dataframe = final_dataframe.sort_index()

        pair_dataframe = pair_dataframe[pair_dataframe['sireId'] != best_result['sireId']]
        pair_dataframe = pair_dataframe[pair_dataframe['sireId'] != best_result['matronId']]
        pair_dataframe = pair_dataframe[pair_dataframe['matronId'] != best_result['sireId']]
        pair_dataframe = pair_dataframe[pair_dataframe['matronId'] != best_result['matronId']]
    
    final_dataframe = final_dataframe.sort_values(by=['return_on_investment'], ascending=False)
    final_dataframe = final_dataframe.astype({'sireId': 'int64', 'matronId': 'int64'})
    return final_dataframe
