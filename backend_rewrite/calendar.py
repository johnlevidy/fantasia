from collections import defaultdict
from functools import partial
import networkx as nx

from .dateutil import busdays_offset

class TaskCalendar:
    """
    Track the assignment of people to tasks on particular dates.
    """

    def __init__(self):
        # Store assignments as {date:{person:[Task]}}.
        self.min_date = None
        self.max_date = None
        self.cal      = defaultdict(partial(defaultdict, list))

    def from_graph(G: nx.DiGraph):
        cal = TaskCalendar()
        for task in G:
            date = task.start_date
            cal.min_date = min(cal.min_date, date) if cal.min_date else date
            est  = task.estimate
            while date < task.end_date and est > 0:
                for assignee in task.assignees:
                    cal.assign(assignee, date, task)
                    date = busdays_offset(date, 1)
                    est -= 1
            cal.max_date = max(cal.max_date, date) if cal.max_date else date
        return cal

    def assign(self, person, date, task):
        self.cal[date][person].append(task)

    def add(self, other):
        for date, people in other.cal.items():
            for person, tasks in people.items():
                for task in tasks:
                    self.assign(person, date, task)
