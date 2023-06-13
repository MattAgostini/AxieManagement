import pickle
import sqlite3 as sql

from dataclasses import dataclass

@dataclass(frozen=False)
class TrackingEntry:
    seed_id: int
    seed_account_num: int
    daily_slp: list
    total_slp: list

class SLPTrackingDatabase:
    TABLE_NAME = 'slp_tracking'

    def __init__(self, dbfile):
        self.dbfile = dbfile
        with sql.connect(self.dbfile) as connection:
            cursor = connection.cursor()
            query = f"CREATE TABLE IF NOT EXISTS {self.TABLE_NAME} (seed_id INTEGER, seed_account_num INTEGER, daily_slp BLOB, total_slp BLOB)"
            cursor.execute(query)
            connection.commit()
            self.last_key = cursor.lastrowid
        self.last_key = None

    def add_slp_tracking_entry(self, account_entry: TrackingEntry):
        with sql.connect(self.dbfile) as connection:
            cursor = connection.cursor()
            query = f"INSERT INTO {self.TABLE_NAME} (seed_id, seed_account_num, daily_slp, total_slp) VALUES (?, ?, ?, ?)"
            cursor.execute(query,
                          (account_entry.seed_id,
                           account_entry.seed_account_num,
                           pickle.dumps(account_entry.daily_slp),
                           pickle.dumps(account_entry.total_slp)))
            connection.commit()
            self.last_key = cursor.lastrowid

    def update_slp_tracking_entry(self, seed_id: int, seed_account_num: int, account_entry: TrackingEntry):
        with sql.connect(self.dbfile) as connection:
            cursor = connection.cursor()
            query = f"UPDATE {self.TABLE_NAME} SET seed_id = ?, seed_account_num = ?, daily_slp = ?, total_slp = ? WHERE (seed_id = ?) AND (seed_account_num = ?)"
            cursor.execute(query,
                          (account_entry.seed_id,
                           account_entry.seed_account_num,
                           pickle.dumps(account_entry.daily_slp),
                           pickle.dumps(account_entry.total_slp),
                           seed_id,
                           seed_account_num))
            connection.commit()

    def get_slp_tracking_entry_from_seed_and_number(self, seed_id: int, seed_account_num: int):
        with sql.connect(self.dbfile) as connection:
            cursor = connection.cursor()
            query = f"SELECT seed_id, seed_account_num, daily_slp, total_slp FROM {self.TABLE_NAME} WHERE (seed_id = ?) AND (seed_account_num = ?)"
            cursor.execute(query, (seed_id, seed_account_num))
            result = cursor.fetchone()
            if result is None: return None
            seed_id, seed_account_num, daily_slp, total_slp = result
        return TrackingEntry(seed_id, seed_account_num, pickle.loads(daily_slp), pickle.loads(total_slp))
