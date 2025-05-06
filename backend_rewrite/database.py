from .database_postgres import PostgresDatabase
from .database_sqlite3 import Sqlite3Database
from typing import Any, List
from urllib.parse import urlparse

class Database:
    def __init__(self, uris: List[str]):
        self.dbs = []
        for uri in uris:
            pr = urlparse(uri)
            if pr.scheme == 'sqlite3':
                self.dbs.append(Sqlite3Database(pr.path))
            elif pr.scheme == 'postgresql' or pr.scheme == 'postgres':
                self.dbs.append(PostgresDatabase(uri))
            else:
                raise ValueError(f"Unsupported database URI: {uri}")
        pass

    def save_schedule(self, project_name: str, calendar: Any):
        for db in self.dbs:
            db.save_schedule(project_name, calendar)
