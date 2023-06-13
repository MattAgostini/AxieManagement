import logging

from backend.parse_axie import createAxieData
from backend.queryMarketplace import MAX_GRAPHQL_QUERY
from backend.parse_accounts import Account
from backend.query_account_axies import query_account_axies
from backend.database.axie_database import AxieEntry
from backend.transaction.transfers import prepare_and_execute_transfer

import backend.transaction.utilities as utilities
import backend.encryption.encryption_util as EncryptUtil
import backend.database.database_util as DbUtil

def refresh_inventory_info(accounts_list: list[Account]):
    logging.info("Refreshing inventories of given scholars")
    accounts_list = [[account] for account in accounts_list]
    inventory_datas = utilities.run_in_parallel(get_inventory_info, accounts_list, 20)
    for inventory_data in inventory_datas:
        account:Account = inventory_data['account']
        account_axies:list = inventory_data['axies']

        entry = DbUtil.account_db.get_account_entry(account.public_addr)
        entry.num_axies = len(account_axies)
        DbUtil.account_db.update_account_entry(account.public_addr, entry)

        DbUtil.axie_db.delete_axies_from_account(account.public_addr)
        for axie_dict in account_axies:
            axie = createAxieData(axie_dict)
            axie_entry = AxieEntry(axie.id, account.public_addr, account, axie)
            DbUtil.axie_db.add_or_update_axie_entry(axie_entry)


def get_inventory_info(account: Account) -> dict:
    query_start = 0
    max_results = True
    account_axies = []
    while max_results:
        axies = query_account_axies(account, query_start)
        if axies is None: break
        account_axies.extend(axies)
        max_results = (len(axies) == MAX_GRAPHQL_QUERY)
        query_start += MAX_GRAPHQL_QUERY
    return {"axies": account_axies, "account": account}


def reclaim_axies():
    transfer_list = {}
    vault_acccounts:list[Account] = []
    for i in range(EncryptUtil.get_seed_count()):
        vault_account = DbUtil.account_db.get_seed_vault_account(i)
        transfer_list[vault_account.public_addr] = []
        vault_acccounts.append(vault_account)

    non_vault_entries = DbUtil.account_db.get_non_vault_entries()
    for non_vault_entry in non_vault_entries:
        if non_vault_entry.discord_id is None and non_vault_entry.num_axies > 0:
            logging.info(f"Reclaiming axies from {non_vault_entry.account}")
            seed_id = non_vault_entry.seed_id
            transfer_list[vault_acccounts[seed_id].public_addr].extend(
                [axie.axie_id for axie in DbUtil.axie_db.get_axies_from_account(non_vault_entry.public_addr)]
            )
    prepare_and_execute_transfer(transfer_list)
