import pickle
import sqlite3 as sql

from dataclasses import dataclass
from backend.parse_accounts import Account, AccountType

@dataclass(frozen=False)
class ScholarPageData:
    unclaimed_slp: int
    slp_to_payout: int
    last_claimed_date: str
    next_claim_status: dict

@dataclass(frozen=False)
class AccountEntry:
    seed_id: int
    seed_account_num: int
    public_addr: str
    account_name: str
    discord_id: str
    num_axies: int
    account: Account
    scholar_page_data: ScholarPageData
    mmr: int

class AccountDatabase:
    TABLE_NAME = 'account'
    ALL_COLUMNS = "seed_id, seed_account_num, addr, name, discord, num_axies, account, scholar_page_data, mmr"

    def __init__(self, dbfile):
        self.dbfile = dbfile
        with sql.connect(self.dbfile) as connection:
            cursor = connection.cursor()
            query = f"CREATE TABLE IF NOT EXISTS {self.TABLE_NAME} (seed_id INTEGER, seed_account_num INTEGER, addr TEXT, name TEXT, discord TEXT, num_axies INTEGER, account BLOB, scholar_page_data BLOB, mmr INTEGER)"
            cursor.execute(query)
            connection.commit()
            self.last_key = cursor.lastrowid
        self.last_key = None

    def add_account_entry(self, account_entry: AccountEntry):
        with sql.connect(self.dbfile) as connection:
            cursor = connection.cursor()
            query = f"INSERT INTO {self.TABLE_NAME} (seed_id, seed_account_num, addr, name, discord, num_axies, account, scholar_page_data, mmr) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
            cursor.execute(query,
                          (account_entry.seed_id,
                           account_entry.seed_account_num,
                           account_entry.public_addr,
                           account_entry.account_name,
                           account_entry.discord_id,
                           account_entry.num_axies,
                           pickle.dumps(account_entry.account),
                           pickle.dumps(account_entry.scholar_page_data),
                           account_entry.mmr))
            connection.commit()
            self.last_key = cursor.lastrowid

    def update_account_entry(self, addr: str, account_entry: AccountEntry):
        with sql.connect(self.dbfile) as connection:
            cursor = connection.cursor()
            query = f"UPDATE {self.TABLE_NAME} SET seed_id = ?, seed_account_num = ?, addr = ?, name = ?, discord = ?, num_axies = ?, account = ?, scholar_page_data = ?, mmr = ? WHERE (addr = ?)"
            cursor.execute(query,
                          (account_entry.seed_id,
                           account_entry.seed_account_num,
                           account_entry.public_addr,
                           account_entry.account_name,
                           account_entry.discord_id,
                           account_entry.num_axies,
                           pickle.dumps(account_entry.account),
                           pickle.dumps(account_entry.scholar_page_data),
                           account_entry.mmr,
                           addr))
            connection.commit()

    def _get_account_entries_from_query(self, query):
        with sql.connect(self.dbfile) as connection:
            cursor = connection.cursor()
            cursor.execute(query)
            account_entries = [AccountEntry(seed_id, seed_account_num, public_addr, account_name, discord, num_axies, pickle.loads(account), pickle.loads(scholar_page_data), mmr)
                               for seed_id, seed_account_num, public_addr, account_name, discord, num_axies, account, scholar_page_data, mmr in cursor]
        return account_entries

    def get_account_entry(self, addr):
        query = f"SELECT {self.ALL_COLUMNS} FROM {self.TABLE_NAME} WHERE (addr = '{addr}')"
        account_entries = self._get_account_entries_from_query(query)
        if not account_entries: return None
        return account_entries[0]

    def get_account_entry_from_seed_and_number(self, seed_id, seed_account_num):
        query = f"SELECT {self.ALL_COLUMNS} FROM {self.TABLE_NAME} WHERE (seed_id = {seed_id}) AND (seed_account_num = {seed_account_num})"
        account_entries = self._get_account_entries_from_query(query)
        if not account_entries: return None
        return account_entries[0]

    def get_account_from_discord_id(self, discord_id):
        query = f"SELECT {self.ALL_COLUMNS} FROM {self.TABLE_NAME} WHERE (discord = {discord_id})"
        account_entries = self._get_account_entries_from_query(query)
        if not account_entries: return None
        return account_entries[0]

    def get_account_entrys(self):
        query = f"SELECT {self.ALL_COLUMNS} FROM {self.TABLE_NAME} ORDER BY seed_id, seed_account_num"
        return self._get_account_entries_from_query(query)

    def get_scholar_entries(self):
        query = f"SELECT {self.ALL_COLUMNS} FROM {self.TABLE_NAME} ORDER BY seed_id, seed_account_num"
        account_entries = self._get_account_entries_from_query(query)
        return [account_entry for account_entry in account_entries if AccountType.Scholar in account_entry.account.account_types]

    def get_non_vault_entries(self):
        query = f"SELECT {self.ALL_COLUMNS} FROM {self.TABLE_NAME} ORDER BY seed_id, seed_account_num"
        account_entries = self._get_account_entries_from_query(query)
        return [account_entry for account_entry in account_entries if AccountType.Vault not in account_entry.account.account_types]

    def get_vault_entries(self):
        query = f"SELECT {self.ALL_COLUMNS} FROM {self.TABLE_NAME} ORDER BY seed_id, seed_account_num"
        account_entries = self._get_account_entries_from_query(query)
        return [account_entry for account_entry in account_entries if AccountType.Vault in account_entry.account.account_types]

    def get_manager_entries(self):
        query = f"SELECT {self.ALL_COLUMNS} FROM {self.TABLE_NAME} ORDER BY seed_id, seed_account_num"
        account_entries = self._get_account_entries_from_query(query)
        return [account_entry for account_entry in account_entries if AccountType.Manager in account_entry.account.account_types]

    def get_seed_account_entries(self, seed_id: int):
        query = f"SELECT {self.ALL_COLUMNS} FROM {self.TABLE_NAME} WHERE (seed_id = {seed_id}) ORDER BY seed_account_num"
        return self._get_account_entries_from_query(query)

    def get_seed_vault_account(self, seed_id: int, enable_assertion: bool = False):
        query = f"SELECT {self.ALL_COLUMNS} FROM {self.TABLE_NAME} WHERE (seed_id = {seed_id})"
        account_entries = self._get_account_entries_from_query(query)
        vault_accounts = [account_entry.account for account_entry in account_entries if AccountType.Vault in account_entry.account.account_types]
        if enable_assertion: assert len(vault_accounts) == 1, "Incorrect number of seed vault accounts found, your database is malformed"
        elif len(vault_accounts) != 1: return None
        return vault_accounts[0]
