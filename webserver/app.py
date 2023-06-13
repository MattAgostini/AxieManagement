import sys
import json
import logging
import pandas as pd
from pathlib import Path
from flask import Flask, render_template, request

from datetime import datetime
from time import sleep
from backend.database.account_database import ScholarPageData

from backend.queryMarketplace import queryMarketplace, MarketplaceSearchCriteria, MAX_GRAPHQL_QUERY
from backend.parse_axie import AxieData, createAxieData
from backend.parse_accounts import Account, AccountType

from backend.transaction.transfers import prepare_and_execute_transfer
from backend.transaction.claims import prepare_and_execute_claim
from backend.transaction.payments import prepare_and_execute_payout

import backend.transaction.utilities as utilities
import backend.encryption.encryption_util as EncryptUtil
import backend.database.database_util as DbUtil
from backend.database.query_database import QueryEntry

from backend.breeding.breeding_calculator import evaluateAxieQuality

import webserver.scholar_page as ScholarPage
import webserver.inventory_page as InventoryPage

app = Flask(__name__)

# Set up logging
path = Path("log/")
path.mkdir(parents=True, exist_ok=True)
logging.getLogger("werkzeug").setLevel(logging.WARNING)
logging.getLogger("urllib3.connectionpool").setLevel(logging.ERROR)
logging.root.handlers = []
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] [%(levelname)s]  %(message)s",
    handlers=[
        logging.FileHandler(path / "webserver-{:%Y-%m-%d}.log".format(datetime.now())),
        logging.StreamHandler(sys.stdout)
    ]
)

@app.route("/")
def index():
    return render_template('index.html')

axie_query = []
MAX_QUERY_SIZE = 2000
@app.route("/search", methods=['GET', 'POST'])
def axie_search():
    global axie_query

    def search_marketplace(query: MarketplaceSearchCriteria) -> list[AxieData]:
        market_axies = []
        query_start = 0
        max_results = True
        while max_results:
            marketplace_dataframe = queryMarketplace(query, query_start)
            axie_dataframe = pd.concat([axie_dataframe, marketplace_dataframe])
            max_results = (len(marketplace_dataframe) == MAX_GRAPHQL_QUERY and query_start < MAX_QUERY_SIZE)
            query_start += MAX_GRAPHQL_QUERY
            logging.info("Getting more results...")
        axies = []
        for i, row in axie_dataframe.iterrows():
            axie = createAxieData(row)
            axie.quality = evaluateAxieQuality(axie, query)
            axies.append(axie)
        return axies


    if request.method == 'POST':

        request_json = request.get_json()
        logging.info(request_json)
        if request_json is not None and request_json['action'] == "search":
            logging.info("Searching marketplace")
            axie_query = []
            query = request_json['query']
            query = MarketplaceSearchCriteria(classes=query['axie_classes'],
                                            eyes=query['axie_eyes'],
                                            ears=query['axie_ears'],
                                            mouth=query['axie_mouths'],
                                            horn=query['axie_horns'],
                                            back=query['axie_backs'],
                                            tail=query['axie_tails'],
                                            breedCount=query['breed_count'],
                                            speed=query['speed'],
                                            hp=query['hp'],
                                            skill=query['skill'],
                                            morale=query['morale'],
                                            min_quality=query['min_quality'])
            axie_query = search_marketplace(query)
            query_entry = QueryEntry('current_query', query)
            DbUtil.query_db.add_or_update_query_entry(query_entry)
        
        if request_json is not None and request_json['action'] == "Save":
            logging.info("Saving search profile")
            query = request_json['query']
            query = MarketplaceSearchCriteria(classes=query['axie_classes'],
                                            eyes=query['axie_eyes'],
                                            ears=query['axie_ears'],
                                            mouth=query['axie_mouths'],
                                            horn=query['axie_horns'],
                                            back=query['axie_backs'],
                                            tail=query['axie_tails'],
                                            breedCount=query['breed_count'],
                                            speed=query['speed'],
                                            hp=query['hp'],
                                            skill=query['skill'],
                                            morale=query['morale'],
                                            min_quality=query['min_quality'])
            query_entry = QueryEntry(request_json['profile'], query)
            DbUtil.query_db.add_or_update_query_entry(query_entry)
            query_entry = QueryEntry('current_query', query)
            DbUtil.query_db.add_or_update_query_entry(query_entry)

        if request_json is not None and request_json['action'] == "Load":
            logging.info("Loading search profile")
            entry = DbUtil.query_db.get_query_entry(request_json['profile'])
            if entry is not None:
                query_entry = QueryEntry('current_query', entry.query)
                DbUtil.query_db.add_or_update_query_entry(query_entry)

        if request_json is not None and request_json['action'] == "Delete":
            logging.info("Deleting search profile")
            DbUtil.query_db.delete_query_entry(request_json['profile'])


    current_query_entry = DbUtil.query_db.get_query_entry('current_query')
    if current_query_entry is None:
        current_query = MarketplaceSearchCriteria(classes=[],
                                                eyes=[],
                                                ears=[],
                                                mouth=[],
                                                horn=[],
                                                back=[],
                                                tail=[],
                                                breedCount=[0, 7],
                                                speed=[27, 61],
                                                hp=[27, 61],
                                                skill=[27, 61],
                                                morale=[27, 61],
                                                min_quality=0)
    else: 
        current_query = current_query_entry.query
                                                
    search_profiles = DbUtil.query_db.get_query_entrys()
    body_parts_json = json.load(open('backend/body-parts.json'))
    return render_template('axie_search.html', 
                        axies=axie_query,
                        query=current_query,
                        search_profiles=search_profiles,
                        body_parts=body_parts_json)


@app.route("/scholar", methods=['GET', 'POST'])
async def axie_scholar():

    async def refresh_scholar_info(scholar_list: list[Account], item_type: utilities.ItemType):
        scholar_list = [[account, item_type] for account in scholar_list]
        scholar_page_datas = utilities.run_in_parallel(ScholarPage.get_scholar_page_data, scholar_list)
        for scholar_page_data in scholar_page_datas:
            scholar:Account = scholar_page_data['scholar']
            scholar_page_data:ScholarPageData = scholar_page_data['scholar_page_data']
            entry = DbUtil.account_db.get_account_entry(scholar.public_addr)
            entry.scholar_page_data = scholar_page_data
            DbUtil.account_db.update_account_entry(scholar.public_addr, entry)


    if request.method == 'POST':
        request_json = request.get_json()

        item_type = utilities.ItemType.SLP
        if request_json['axs_mode']: item_type = utilities.ItemType.mAXS

        if request_json is not None and request_json['action'] == "set_vault":
            seed_id = request_json['seed_id']
            seed_account_num = request_json['seed_account_num']
            vault_account = DbUtil.account_db.get_seed_vault_account(seed_id)
            if vault_account is not None:
                old_vault = DbUtil.account_db.get_account_entry_from_seed_and_number(vault_account.seed_id, vault_account.seed_account_num)
                old_vault.account.account_types.remove(AccountType.Vault)
                DbUtil.account_db.update_account_entry(old_vault.public_addr, old_vault)
            new_vault = DbUtil.account_db.get_account_entry_from_seed_and_number(seed_id, seed_account_num)
            new_vault.account.account_types.append(AccountType.Vault)
            DbUtil.account_db.update_account_entry(new_vault.public_addr, new_vault)

        if request_json is not None and request_json['action'] == "refresh":
            logging.info("Refreshing SLP data for selected accounts")
            scholar_addrs_selected = request_json['scholar_list']
            scholars_selected = [DbUtil.account_db.get_account_entry(addr).account for addr in scholar_addrs_selected]
            await refresh_scholar_info(scholars_selected, item_type)

        if request_json is not None and request_json['action'] == "refresh_mmr":
            logging.info("Refreshing MMR data for selected accounts")
            scholar_addrs_selected = request_json['scholar_list']
            scholars_selected = [DbUtil.account_db.get_account_entry(addr) for addr in scholar_addrs_selected]
            await ScholarPage.refresh_scholar_mmr(scholars_selected)

        if request_json is not None and request_json['action'] == "claim":
            logging.info("Claiming SLP from selected accounts")
            scholar_addrs_selected = request_json['scholar_list']
            scholars_selected = [DbUtil.account_db.get_account_entry(addr).account for addr in scholar_addrs_selected]
            prepare_and_execute_claim(scholars_selected, item_type)
            await refresh_scholar_info(scholars_selected, item_type)

        if request_json is not None and request_json['action'] == "payout":
            logging.info("Paying out SLP from selected accounts")
            scholar_addrs_selected = request_json['scholar_list']
            scholars_selected = [DbUtil.account_db.get_account_entry(addr).account for addr in scholar_addrs_selected]
            prepare_and_execute_payout(scholars_selected, item_type)
            await refresh_scholar_info(scholars_selected, item_type)

    scholar_infos = DbUtil.account_db.get_non_vault_entries()
    vault_infos = ScholarPage.get_vault_page_info()
    return render_template('axie_scholar.html',
                            scholarInfos=scholar_infos,
                            vault_infos=vault_infos)


axie_infos = []
@app.route("/inventory", methods=['GET', 'POST'])
def axie_inventory():
    global axie_infos
    if request.method == 'POST':
        axie_infos = []
        request_json = request.get_json()
        if request_json is not None and request_json['action'] == "refresh":
            addresses_to_refresh = request_json['inventory_list']
            accounts_to_refresh = [DbUtil.account_db.get_account_entry(address).account for address in addresses_to_refresh]
            InventoryPage.refresh_inventory_info(accounts_to_refresh)

        if request_json is not None and request_json['action'] == "load":
            logging.info("Loading inventories")
            addresses_to_load = request_json['inventory_list']
            for address in addresses_to_load:
                axie_infos.extend(DbUtil.axie_db.get_axies_from_account(address))

        if request_json is not None and request_json['action'] == "transfer":
            transfer_list = request_json['transfer_list']
            refresh_list = prepare_and_execute_transfer(transfer_list)
            logging.info("Giving the server some buffering time")
            sleep(60)
            InventoryPage.refresh_inventory_info(refresh_list)

        if request_json is not None and request_json['action'] == "reclaim":
            accounts = [entry.account for entry in DbUtil.account_db.get_account_entrys()]
            InventoryPage.refresh_inventory_info(accounts)
            InventoryPage.reclaim_axies()
            logging.info("Giving the server some buffering time")
            sleep(60)
            InventoryPage.refresh_inventory_info(accounts)

    non_vault_inventories = DbUtil.account_db.get_non_vault_entries()
    vault_inventories = DbUtil.account_db.get_vault_entries()
    return render_template('axie_inventory.html',
                            vault_inventories=vault_inventories,
                            non_vault_inventories=non_vault_inventories,
                            axie_infos=axie_infos)


def run():
    logging.info("Running Axie Management software!")
    EncryptUtil.login()
    logging.info("Running on http://127.0.0.1:5000/")
    app.run()
