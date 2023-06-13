import requests
import json
import pandas as pd

ETH = 'eth'
AXS = 'axs'
SLP = 'slp'

USD = 'usd'
PHP = 'php'

def query_coin_base(currency: str):
    url = f'https://api.coingecko.com/api/v3/coins/markets?vs_currency={currency}&ids=ethereum,smooth-love-potion,axie-infinity&locale=en'
    response = requests.get(url)
    if response.status_code != 200:
        print(f'{response.status_code}: Error retrieving data from coin base')

    json_data = json.loads(response.text)
    df = pd.DataFrame(json_data)

    parsed_df = df[['id', 'symbol', 'name', 'current_price']]
    return parsed_df

def get_exchange_rate(coinbaseDataframe: pd.DataFrame, key: str):
    coin_df = coinbaseDataframe.loc[coinbaseDataframe['symbol'] == key]
    return coin_df.iloc[0]['current_price']
