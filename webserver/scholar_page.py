import logging

from datetime import timedelta, datetime

import backend.encryption.encryption_util as EncryptUtil
import backend.transaction.utilities as utilities
import backend.database.database_util as DbUtil
from backend.parse_accounts import Account
from backend.transaction.claims import get_slp_data, get_token_data
from backend.database.account_database import AccountEntry
from backend.query_game_api import make_json_request


def get_scholar_page_data(scholar: Account, item_type: utilities.ItemType) -> dict:
    scholar_page_data = DbUtil.initialize_scholar_page_data()
    token_info_dict = get_token_data(scholar, item_type)
    if token_info_dict is None: 
        logging.error(f"Failed to get slp data for {scholar}")
        scholar_page_data.last_claimed_date = {"display": f'Error getting SLP data!', "style": "not_ready"}
        return {"scholar_page_data": scholar_page_data, "scholar": scholar, "slp_info_dict": token_info_dict}

    unclaimed_slp = token_info_dict['rawTotal'] - token_info_dict['rawClaimableTotal']
    if item_type == utilities.ItemType.mAXS: unclaimed_slp = token_info_dict['claimableTotal']

    slp_to_payout = utilities.check_balance(scholar)
    if item_type == utilities.ItemType.mAXS: slp_to_payout = utilities.check_balance(scholar, 'axs') / (10 ** 18)

    last_claimed_date = datetime.fromtimestamp(token_info_dict['lastClaimedItemAt'])
    next_claim_date = last_claimed_date + timedelta(days=14)
    date_format_string = "%Y-%m-%d %H:%M:%S"
    last_claimed_date_formatted = datetime.strftime(last_claimed_date, date_format_string)
    next_claim_date_formatted = datetime.strftime(next_claim_date, date_format_string)

    # Provide status information based on current date, and date of next claim
    next_claim_status = {"display": f'Next Claim: {next_claim_date_formatted}', "style": "not_ready"}
    if datetime.now() > next_claim_date:
        next_claim_status = {"display": f'Ready', "style": "ready"}

    scholar_page_data.unclaimed_slp = unclaimed_slp
    scholar_page_data.slp_to_payout = slp_to_payout
    scholar_page_data.last_claimed_date = last_claimed_date_formatted
    scholar_page_data.next_claim_status = next_claim_status
    return {"scholar_page_data": scholar_page_data, "scholar": scholar, "slp_info_dict": token_info_dict}


def get_vault_page_info() -> list[dict]:
    vault_infos = []
    for seed_id in range(EncryptUtil.get_seed_count()):
        seed_account_entries = DbUtil.account_db.get_seed_account_entries(seed_id)
        vault_account = DbUtil.account_db.get_seed_vault_account(seed_id)
        vault_infos.append({
            "vault_account": vault_account,
            "num_accounts" : len(seed_account_entries)
        })
    return vault_infos


GAME_API = "https://game-api-pre.skymavis.com"
async def refresh_scholar_mmr(entries: AccountEntry) -> None:

    def get_account_mmr(account_entry: AccountEntry):
        access_token = utilities.generate_access_token(account_entry.account)
        if access_token is None:
            logging.error(f"Failed to get auth token for daily for {account_entry.public_addr}")
            return

        ronin_addr = account_entry.public_addr.replace("ronin:", "0x")
        urlBattle = f"{GAME_API}/leaderboard?client_id={ronin_addr}&offset=0&limit=0"
        jsonDatBattle = make_json_request(urlBattle, access_token)
        if jsonDatBattle is None:
            return {"mmr": -1, "account_entry": account_entry}

        player = jsonDatBattle['items'][1]
        mmr = int(player["elo"])

        account_entry.mmr = mmr
        DbUtil.account_db.update_account_entry(account_entry.public_addr, account_entry)
        return {"mmr": mmr, "account_entry": account_entry}

    entries = [[entry] for entry in entries]
    mmr_datas = utilities.run_in_parallel(get_account_mmr, entries)
    for mmr_data in mmr_datas:
        account_entry:AccountEntry = mmr_data['account_entry']
        mmr = mmr_data['mmr']
        account_entry.mmr = mmr
        DbUtil.account_db.update_account_entry(account_entry.public_addr, account_entry)
