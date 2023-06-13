import pickle
import sqlite3 as sql

from dataclasses import dataclass

from backend.queryMarketplace import MarketplaceSearchCriteria


@dataclass(frozen=False)
class QueryEntry:
    name: str
    query: MarketplaceSearchCriteria

class QueryDatabase:
    def __init__(self, dbfile):
        self.dbfile = dbfile
        with sql.connect(self.dbfile) as connection:
            cursor = connection.cursor()
            query = "create table if not exists SEARCH (NAME TEXT, QUERY BLOB)"
            cursor.execute(query)
            connection.commit()
            self.last_key = cursor.lastrowid
        self.last_key = None

    def add_query_entry(self, query_entry: QueryEntry):
        with sql.connect(self.dbfile) as connection:
            cursor = connection.cursor()
            query = "INSERT INTO SEARCH (NAME, QUERY) VALUES (?, ?)"
            cursor.execute(query,
                          (query_entry.name,
                           pickle.dumps(query_entry.query)))
            connection.commit()
            self.last_key = cursor.lastrowid

    def delete_query_entry(self, id):
        with sql.connect(self.dbfile) as connection:
            cursor = connection.cursor()
            query = "DELETE FROM SEARCH WHERE (NAME = ?)"
            cursor.execute(query, (id,))
            connection.commit()

    def update_query_entry(self, id: str, query_entry: QueryEntry):
        with sql.connect(self.dbfile) as connection:
            cursor = connection.cursor()
            query = "UPDATE SEARCH SET NAME = ?, QUERY = ? WHERE (NAME = ?)"
            cursor.execute(query,
                          (query_entry.name,
                           pickle.dumps(query_entry.query),
                           id))
            connection.commit()

    def add_or_update_query_entry(self, query_entry: QueryEntry):
        if self.get_query_entry(query_entry.name) == None:
            self.add_query_entry(query_entry)
        else:
            self.update_query_entry(query_entry.name, query_entry)

    def get_query_entry(self, id):
        with sql.connect(self.dbfile) as connection:
            cursor = connection.cursor()
            query = "SELECT NAME, QUERY FROM SEARCH WHERE (NAME = ?)"
            cursor.execute(query, (id,))
            result = cursor.fetchone()
            if result == None: return None
            name, query = result
        return QueryEntry(name, pickle.loads(query))

    def get_query_entrys(self):
        with sql.connect(self.dbfile) as connection:
            cursor = connection.cursor()
            query = "SELECT NAME, QUERY FROM SEARCH ORDER BY NAME"
            cursor.execute(query)
            queries = [QueryEntry(name, pickle.loads(query))
                     for name, query in cursor]
        return queries
