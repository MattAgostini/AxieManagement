import time
import logging
import requests

from backend.parse_accounts import Account

def query_account_axies(account: Account, start: int, size: int = 100, attempts: int = 0):
    ronin = account.public_addr.replace("ronin:", "0x")

    payload = {
        "operationName": "GetAxieBriefList",
        "variables": {
            "from": start,
            "size": size,
            "auctionType": "All",
            "owner": ronin
        },
        "query": """query GetAxieBriefList($auctionType: AuctionType, $criteria: AxieSearchCriteria, $from: Int, $sort: SortBy, $size: Int, $owner: String) {
            axies(auctionType: $auctionType, criteria: $criteria, from: $from, sort: $sort, size: $size, owner: $owner) {   
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
    }

    url = 'https://graphql-gateway.axieinfinity.com/graphql'

    try: 
        response = requests.post(url, json=payload)
        json_data = response.json()
        axie_data = json_data['data']['axies']['results']
        return axie_data
    except:
        if attempts < 5: 
            time.sleep(3)
            return query_account_axies(account, start, size, attempts + 1)
        else:
            logging.critical(f'{response.status_code}: Error retrieving axie data from {account}')
            return None
