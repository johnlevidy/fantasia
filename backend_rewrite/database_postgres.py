import psycopg2
import time

from .calendar import TaskCalendar
from .types import StatusCanonicalOrdinal

class PostgresDatabase:
    def __init__(self, uri: str):
        print(f"Connecting to postgres database at {uri}")
        self.conn = psycopg2.connect(uri)
        with self.conn: 
            with self.conn.cursor() as c:
                c.execute("""
                    CREATE TABLE IF NOT EXISTS projects (
                        id SERIAL PRIMARY KEY,
                        name TEXT NOT NULL UNIQUE,
                        last_updated_ns BIGINT NOT NULL)
                """)
                c.execute("""
                    CREATE TABLE IF NOT EXISTS schedules (
                        id SERIAL PRIMARY KEY,
                        project_id INTEGER NOT NULL,
                        created_ns BIGINT NOT NULL,
                        FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE)
                """)
                c.execute("""
                    CREATE TABLE IF NOT EXISTS tasks (
                        id SERIAL PRIMARY KEY,
                        schedule_id INTEGER NOT NULL,
                        task TEXT NOT NULL,
                        date DATE NOT NULL,
                        assignee TEXT NOT NULL,
                        status SMALLINT NOT NULL,
                        FOREIGN KEY (schedule_id) REFERENCES schedules(id) ON DELETE CASCADE)
                """)

    def save_schedule(self, project_name: str, calendar: TaskCalendar):
        with self.conn:
            with self.conn.cursor() as c:
                # First, get the project id; record the current time as the last updated time.
                c.execute("""
                    INSERT INTO projects (name, last_updated_ns) VALUES (%s, %s) 
                    ON CONFLICT (name) DO UPDATE SET last_updated_ns = excluded.last_updated_ns 
                    RETURNING id""", (project_name, time.time_ns()))
                project_id = c.fetchone()[0]

                # Create a new schedules entry.
                c.execute("""
                    INSERT INTO schedules (project_id, created_ns) VALUES (%s, %s) 
                    RETURNING id""", (project_id, time.time_ns()))
                schedule_id = c.fetchone()[0]

                # Now write all the tasks in the calendar.
                for date, people in calendar.cal.items():
                    for person, tasks in people.items():
                        for task in tasks:
                            c.execute("""
                                INSERT INTO tasks (schedule_id, task, date, assignee, status) VALUES (%s, %s, %s, %s, %s)""",
                                (schedule_id, task.name, date, person, StatusCanonicalOrdinal[task.status]))

    def __del__(self):
        if self.conn:
            self.conn.close()
