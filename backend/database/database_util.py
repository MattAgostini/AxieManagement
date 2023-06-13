import sqlite3 as sql
import numpy as np
from backend.database.query_database import QueryDatabase

from backend.parse_accounts import Account, parse_account_file

from backend.database.account_database import AccountDatabase, AccountEntry, ScholarPageData
from backend.database.axie_database import AxieDatabase
from backend.database.slp_tracking_database import SLPTrackingDatabase, TrackingEntry


DATABASE_FILE = "database.sqlite"
SLP_TRACKING_DATABASE_FILE = "slp_tracking.sqlite"

account_db = AccountDatabase(DATABASE_FILE)
axie_db = AxieDatabase(DATABASE_FILE)
query_db = QueryDatabase(DATABASE_FILE)
slp_tracking_db = SLPTrackingDatabase(SLP_TRACKING_DATABASE_FILE)

def initialize_database():
    accounts_list:list[Account] = []
    parse_account_file(accounts_list)
    for account in accounts_list: initialize_account(account)


def initialize_scholar_page_data() -> ScholarPageData:
    return ScholarPageData(0, 0, "0", {"display": 'Error: database entry unpopulated', "style": "not_ready"})


def initialize_account(account: Account):
    scholar_page_data = initialize_scholar_page_data()
    account_entry = AccountEntry(account.seed_id, account.seed_account_num, account.public_addr, account.account_name, account.discord_id, -1, account, scholar_page_data, -1)
    account_db.add_account_entry(account_entry)

    tracking_entry = TrackingEntry(account.seed_id, account.seed_account_num, np.zeros((60)), np.zeros((60)))
    slp_tracking_db.add_slp_tracking_entry(tracking_entry)


def clear_database():
    table_names = [
        account_db.TABLE_NAME,
        "AXIES",
        "SEARCH"
    ]
    with sql.connect(DATABASE_FILE) as connection:
        for table_name in table_names:
            cursor = connection.cursor()
            query = f"DELETE FROM {table_name}"
            cursor.execute(query)
            connection.commit()
