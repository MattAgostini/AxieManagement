import logging
import asyncio
import typing
import urllib3
import functools
import json
import os
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

import backend.transaction.utilities as utilities
import backend.database.database_util as DbUtil
from backend.parse_accounts import Account, DEFAULT_ACCOUNT_NAME
from backend.transaction.claims import get_slp_data
from backend.transaction.transfers import prepare_and_execute_transfer
from backend.transaction.claims import prepare_and_execute_claim
from backend.transaction.payments import prepare_and_execute_payout, DEVELOPER_FEE

import webserver.scholar_page as ScholarPage

# setup requests pool
retryAmount = 3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
retries = urllib3.Retry(connect=retryAmount, read=retryAmount, redirect=2, status=retryAmount, status_forcelist=[502, 503])
http = urllib3.PoolManager(retries=retries)

GAME_API = "https://game-api-pre.skymavis.com"

def to_thread(func: typing.Callable) -> typing.Coroutine:
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        return await asyncio.to_thread(func, *args, **kwargs)
    return wrapper


@to_thread
def claim_all():
    non_vault_entries = DbUtil.account_db.get_non_vault_entries()
    non_vault_accounts = [entry.account for entry in non_vault_entries]
    prepare_and_execute_claim(non_vault_accounts)

@to_thread
def payout_all():
    non_vault_entries = DbUtil.account_db.get_non_vault_entries()
    non_vault_accounts = [entry.account for entry in non_vault_entries]
    prepare_and_execute_payout(non_vault_accounts)

@to_thread
def reclaim_axies(seed_id: int, seed_account_num: int):
    vault_entry =  DbUtil.account_db.get_seed_vault_account(seed_id)
    account_entry = DbUtil.account_db.get_account_entry_from_seed_and_number(seed_id, seed_account_num)
    account_axies = DbUtil.axie_db.get_axies_from_account(account_entry.public_addr)

    transfer_list = {vault_entry.public_addr: [axie_entry.axie_id for axie_entry in account_axies]}
    prepare_and_execute_transfer(transfer_list)
    

@to_thread
def update_databases_with_tracker():
    account_entries = [entry for entry in DbUtil.account_db.get_account_entrys()]
    account_list = [[account_entry.account] for account_entry in account_entries]
    account_scholar_page_datas = utilities.run_in_parallel(ScholarPage.get_scholar_page_data, account_list)
    for page_data in account_scholar_page_datas:
        account:Account = page_data['scholar']
        scholar_page_data = page_data['scholar_page_data']
        account_entry = DbUtil.account_db.get_account_entry(account.public_addr)
        account_entry.scholar_page_data = scholar_page_data
        DbUtil.account_db.update_account_entry(account.public_addr, account_entry)

        current_slp = page_data['slp_info_dict']['rawTotal']
        tracking_entry = DbUtil.slp_tracking_db.get_slp_tracking_entry_from_seed_and_number(account_entry.seed_id, account_entry.seed_account_num)

        tracking_entry.total_slp = np.roll(tracking_entry.total_slp, -1)
        tracking_entry.total_slp[-1] = current_slp
        
        tracking_entry.daily_slp = np.roll(tracking_entry.daily_slp, -1)
        tracking_entry.daily_slp[-1] = tracking_entry.total_slp[-1] - tracking_entry.total_slp[-2]
        DbUtil.slp_tracking_db.update_slp_tracking_entry(account_entry.seed_id, account_entry.seed_account_num, tracking_entry)


@to_thread
def build_accounts_spreadsheet(bot) -> str:
    account_entries = DbUtil.account_db.get_account_entrys()
    data = []
    for entry in account_entries:
        discord_user_name = None
        if entry.discord_id is not None:
            discord_user = bot.get_user(int(entry.discord_id))
            discord_user_name = str(discord_user)
        account_types = None
        if len(entry.account.account_types) > 0:
            account_types = '/'.join([account_type.value for account_type in entry.account.account_types])
        account_name = entry.account_name
        if account_name == DEFAULT_ACCOUNT_NAME: account_name = None
        data.append([entry.seed_id, entry.seed_account_num, account_name, discord_user_name, entry.discord_id, account_types, entry.public_addr, entry.account.account_email,
                        entry.account.account_password, entry.mmr, entry.num_axies, entry.scholar_page_data.slp_to_payout, entry.account.payout_addr, entry.account.payout_percentage])
    table = pd.DataFrame(data, columns=['seed_id', 'seed_account_num', 'name', 'discord_name', 'discord_id', 'account_type', 'ronin_addr', 'account_email', 
                                        'account_password', 'mmr', 'num_axies', 'slp', 'payout_addr', 'payout_percentage'])

    date_format_string = "%Y-%m-%d_%H-%M-%S"
    fName = os.getcwd() + f'/accounts_{datetime.strftime(datetime.now(), date_format_string)}.xlsx'

    writer = pd.ExcelWriter(fName, engine='xlsxwriter')
    table.to_excel(writer, sheet_name='Sheet1', index=False)

    worksheet = writer.sheets['Sheet1']
    worksheet.set_column('B:N', 20)
    worksheet.set_column('G:G', 50)
    worksheet.set_column('H:H', 40)
    worksheet.set_column('M:M', 50)

    writer.close()
    return fName

@to_thread
def build_daily_report_spreadsheet() -> str:
    entries = [
        entry for entry in DbUtil.account_db.get_scholar_entries() 
        if entry.account.account_name != DEFAULT_ACCOUNT_NAME and entry.num_axies > 0
    ]

    tracking_entry_length = 0
    data = []
    for entry in entries:
        slp_tracking_entry = DbUtil.slp_tracking_db.get_slp_tracking_entry_from_seed_and_number(entry.seed_id, entry.seed_account_num)
        tracking_entry_length = len(slp_tracking_entry.daily_slp)
        weekly_avg = round(sum(slp_tracking_entry.daily_slp[-7:]) / len(slp_tracking_entry.daily_slp[-7:]))
        data.append([entry.seed_id, entry.seed_account_num, entry.account_name, entry.mmr, weekly_avg, *(np.flip(slp_tracking_entry.daily_slp))])

    date_format_string = "%Y-%m-%d"
    current_date = datetime.now()
    dates = []
    for i in range(tracking_entry_length):
        dates.append(datetime.strftime(current_date + timedelta(days=-i), date_format_string))
    current_date = datetime.now()
    table = pd.DataFrame(data, columns=['seed_id', 'seed_account_num', 'name', 'mmr', "7 Day Avg", *dates])

    fName = os.getcwd() + f'/summary_detailed_{datetime.strftime(datetime.now(), date_format_string)}.xlsx'
    writer = pd.ExcelWriter(fName, engine='xlsxwriter')
    table.to_excel(writer, sheet_name='Sheet1', index=False)

    workbook = writer.book
    red_format = workbook.add_format({'bg_color': '#FFC7CE',
                                   'font_color': '#9C0006'})
    green_format = workbook.add_format({'bg_color': '#C6EFCE',
                                   'font_color': '#006100'})

    worksheet = writer.sheets['Sheet1']
    worksheet.set_column('C:C', 20)
    worksheet.set_column('D:BM', 15)
    worksheet.conditional_format(f'E2:BM{len(table) + 1}', 
                                {'type': 'cell',
                                 'criteria': '>=',
                                 'value': 150,
                                 'format': green_format})
    worksheet.conditional_format(f'E2:BM{len(table) + 1}', 
                                {'type': 'cell',
                                 'criteria': '<',
                                 'value': 150,
                                 'format': red_format})

    writer.close()
    return fName


def makeJsonRequest(url, token, attempt = 0):
    response = None
    jsonDat = None
    try:
        response = http.request(
            "GET",
            url,
            headers={
                "Host": "game-api.skymavis.com",
                "User-Agent": "UnityPlayer/2019.4.28f1 (UnityWebRequest/1.0, libcurl/7.52.0-DEV)",
                "Accept": "*/*",
                "Accept-Encoding": "identity",
                "Authorization": 'Bearer ' + token,
                "X-Unity-Version": "2019.4.28f1"
            }
        )

        jsonDat = json.loads(response.data.decode('utf8'))  # .decode('utf8')
        succ = False
        if 'success' in jsonDat:
            succ = jsonDat['success']

        if 'story_id' in jsonDat:
            succ = True

        if not succ:
            if 'details' in jsonDat and len(jsonDat['details']) > 0:
                if 'code' in jsonDat:
                    logging.error(f"API call failed in makeJsonRequest for: {url}, {jsonDat['code']}, attempt {attempt}")
                else:
                    logging.error(f"API call failed in makeJsonRequest for: {url}, {jsonDat['details'][0]}, attempt {attempt}")
            else:
                logging.error(f"API call failed in makeJsonRequest for: {url}, attempt {attempt}")

            if attempt < 3:
                return makeJsonRequest(url, token, attempt + 1)
            else:
                return None

    except Exception as e:
        logging.error(f"Exception in makeJsonRequest for: {url}, attempt {attempt}")
        logging.error(response.data.decode('utf8'))
        if attempt < 3:
            return makeJsonRequest(url, token, attempt + 1)
        else:
            return None

    return jsonDat
