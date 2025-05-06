import sqlite3
import time

from .calendar import TaskCalendar
from .types import StatusCanonicalOrdinal

class Sqlite3Database:
    YYYYMMDD = "%Y%m%d"

    def __init__(self, path: str):
        print(f"Connecting to sqlite database at {path}")
        self.path = path

        # Set up the database.
        with sqlite3.connect(self.path) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS projects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    last_updated_ns INTEGER NOT NULL)
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS schedules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL,
                    created_ns INTEGER NOT NULL,
                    FOREIGN KEY (project_id) REFERENCES projects(id))
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    schedule_id INTEGER NOT NULL,
                    task TEXT NOT NULL,
                    date INTEGER NOT NULL,
                    assignee TEXT NOT NULL,
                    status INTEGER NOT NULL,
                    FOREIGN KEY (schedule_id) REFERENCES schedules(id))
            """)

    def get_connection(self):
        from flask import g
        if "conn" not in g:
            g.conn = sqlite3.connect(self.path)
            g.conn.execute("PRAGMA foreign_keys = ON")
        return g.conn

    def save_schedule(self, project_name: str, calendar: TaskCalendar):
        with self.get_connection() as conn:
            # First, get the project id; record the current time as the last updated time.
            project_id = conn.execute("""
                INSERT INTO projects (name, last_updated_ns) VALUES (?, ?) 
                ON CONFLICT (name) DO UPDATE SET last_updated_ns = excluded.last_updated_ns 
                RETURNING id""", (project_name, time.time_ns())).fetchone()[0]

            # Create a new schedules entry.
            schedule_id = conn.execute("""
                INSERT INTO schedules (project_id, created_ns) VALUES (?, ?) 
                RETURNING id""", (project_id, time.time_ns())).fetchone()[0]

            # Now write all the tasks in the calendar.
            for date, people in calendar.cal.items():
                for person, tasks in people.items():
                    for task in tasks:
                        conn.execute("""
                            INSERT INTO tasks (schedule_id, task, date, assignee, status) VALUES (?, ?, ?, ?, ?)""",
                            (schedule_id, task.name, int(date.strftime(self.YYYYMMDD)), person, StatusCanonicalOrdinal[task.status]))

    def __del__(self):
        from flask import g
        conn = g.pop('conn', None)
        if conn:
            conn.close()
