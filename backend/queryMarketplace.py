import logging
import requests
import json
import pandas as pd
from dataclasses import dataclass

AUCTION_TYPE = "Sale"
SORT_BY = "PriceAsc"
MAX_GRAPHQL_QUERY = 100

@dataclass(frozen=True, eq=True)
class MarketplaceSearchCriteria:

    classes: list
    eyes: list
    ears: list
    mouth: list
    horn: list
    back: list
    tail: list

    breedCount: list

    hp: list
    speed: list
    skill: list
    morale: list

    min_quality: int

    def __hash__(self) -> int:
        return hash(str(self))

    def __repr__(self):
        output_string = "{"

        output_string += "classes: ["
        for id, axie_class in enumerate(self.classes):
            output_string += axie_class
            if id != len(self.classes) - 1: output_string += ','
        output_string += "]"
        output_string += ","

        parts = [*self.mouth, *self.horn, *self.back, *self.tail]
        output_string += " parts: ["
        for id, part in enumerate(parts):
            output_string += '"' + part['partId'] + '"'
            if id != len(parts) - 1: output_string += ','
        output_string += "]"
        output_string += ","

        output_string += f' breedCount: [{self.breedCount[0]}, {self.breedCount[1]}],'
        output_string += f' hp: [{self.hp[0]}, {self.hp[1]}],'
        output_string += f' speed: [{self.speed[0]}, {self.speed[1]}]'
        output_string += f' skill: [{self.skill[0]}, {self.skill[1]}]'
        output_string += f' morale: [{self.morale[0]}, {self.morale[1]}]'

        output_string += "}"
        return output_string


def queryMarketplace(criteria: MarketplaceSearchCriteria, start: int, size: int = MAX_GRAPHQL_QUERY):
    query = \
    "query {" \
        "axies(auctionType: " + AUCTION_TYPE + ", criteria:" + str(criteria) + ", from: " + str(start) + ", sort: " + SORT_BY + ", size: " + str(size) + ") {" """\
            total
            results {
                ...AxieBrief
                __typename
            }
            __typename
        }
    }

    fragment AxieBrief on Axie {
        id
        name
        stage
        class
        breedCount
        image

        genes
        sireId

        battleInfo {
            banned
        }

        auction {
            currentPrice
            currentPriceUSD
        }
    }
    """

    url = 'https://graphql-gateway.axieinfinity.com/graphql'
    response = requests.post(url, json={'query': query})
    if response.status_code != 200:
        logging.error(f'{response.status_code}: Error retrieving data from martketplace')

    json_data = json.loads(response.text)

    retries = 10
    while json_data['data'] == None and retries != 0:
        logging.error(f'{response.status_code}: Error retrieving data from martketplace... retrying')
        response = requests.post(url, json={'query': query})
        json_data = json.loads(response.text)
        retries -= 1

    df_data = json_data['data']['axies']
    df_axie_data = df_data['results']
    df = pd.json_normalize(df_axie_data)

    return df
