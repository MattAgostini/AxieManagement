import pickle
import sqlite3 as sql

from dataclasses import dataclass
from backend.parse_axie import AxieData
from backend.parse_accounts import Account


@dataclass(frozen=False)
class AxieEntry:
    axie_id: int
    owner_addr: str
    owner_account: Account # TODO: We shouldn't really store this information here (Should be joining with account table)
    axie: AxieData

class AxieDatabase:
    TABLE_NAME = 'account'

    def __init__(self, dbfile):
        self.dbfile = dbfile
        with sql.connect(self.dbfile) as connection:
            cursor = connection.cursor()
            query = "CREATE TABLE IF NOT EXISTS axies (id INTEGER, addr TEXT, account BLOB, axie BLOB)"
            cursor.execute(query)
            connection.commit()
            self.last_key = cursor.lastrowid
        self.last_key = None

    def add_axie_entry(self, axie_entry: AxieEntry):
        with sql.connect(self.dbfile) as connection:
            cursor = connection.cursor()
            query = "INSERT INTO axies (id, addr, account, axie) VALUES (?, ?, ?, ?)"
            cursor.execute(query,
                          (axie_entry.axie_id,
                           axie_entry.owner_addr,
                           pickle.dumps(axie_entry.owner_account),
                           pickle.dumps(axie_entry.axie)))
            connection.commit()
            self.last_key = cursor.lastrowid

    def update_axie_entry(self, id: str, axie_entry: AxieEntry):
        with sql.connect(self.dbfile) as connection:
            cursor = connection.cursor()
            query = "UPDATE axies SET id = ?, addr = ?, account = ?, axie = ? WHERE (id = ?)"
            cursor.execute(query,
                          (axie_entry.axie_id,
                           axie_entry.owner_addr,
                           pickle.dumps(axie_entry.owner_account),
                           pickle.dumps(axie_entry.axie),
                           id))
            connection.commit()

    def delete_axies_from_account(self, addr):
        with sql.connect(self.dbfile) as connection:
            cursor = connection.cursor()
            query = "DELETE FROM axies WHERE (addr = ?)"
            cursor.execute(query, (addr,))
            connection.commit()

    def add_or_update_axie_entry(self, axie_entry: AxieEntry):
        if self.get_axie_entry(axie_entry.axie_id) == None:
            self.add_axie_entry(axie_entry)
        else:
            self.update_axie_entry(axie_entry.axie_id, axie_entry)

    def get_axie_entry(self, id):
        with sql.connect(self.dbfile) as connection:
            cursor = connection.cursor()
            query = "SELECT id, addr, account, axie FROM axies WHERE (ID = ?)"
            cursor.execute(query, (id,))
            result = cursor.fetchone()
            if result == None: return None
            axie_id, owner_addr, account, axie = result
        return AxieEntry(axie_id, owner_addr, pickle.loads(account), pickle.loads(axie))

    def get_axies_from_account(self, addr):
        with sql.connect(self.dbfile) as connection:
            cursor = connection.cursor()
            query = "SELECT id, addr, account, axie FROM axies WHERE (ADDR = ?)"
            cursor.execute(query, (addr,))
            axies = [AxieEntry(axie_id, owner_addr, pickle.loads(account), pickle.loads(axie))
                     for axie_id, owner_addr, account, axie in cursor]
        return axies
