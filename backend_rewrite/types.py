from dataclasses import dataclass, field
from typing import Optional
from enum import Enum, StrEnum, auto
from datetime import date

SOON_THRESHOLD = 3

# Edges only have dicts to store data; use a StrEnum to define the keys we use.
class Edge(StrEnum):
    weight   = auto()  # int; the weight of the edge, based on the ancestor task estimate.
    slack    = auto()  # int; the number of business days difference between the task's end date and the start of the next. Assigned to edges.
    critical = auto()  # bool; True if this edge is on the critical path.

@dataclass
class Person:
    name: str

    def __hash__(self) -> int:
        return hash(self.name)

class Status(StrEnum):
    InProgress = 'in progress'
    Blocked = 'blocked' 
    Milestone = 'milestone'
    Completed = 'completed'
    NotStarted = 'not started'

StatusNormalization: dict[str, Status] = {
    'in progress' : (Status.InProgress),
    'blocked' : (Status.Blocked),
    'milestone' : (Status.Milestone),
    'completed' : (Status.Completed),
    'not started': (Status.NotStarted),
    '': (Status.NotStarted),
    'in review': (Status.InProgress),
    'investigating': (Status.InProgress),
    'on hold': (Status.InProgress),
    'waiting': (Status.InProgress),
    'paused': (Status.InProgress)
}

def parse_status(status: str) -> Status:
    return StatusNormalization[status] if status in StatusNormalization else Status[status]

# Scheduler tasks are more granular
# and contain only the absolutely essential information
# for the solver
@dataclass
class SchedulerFields:
    id: int
    eligible_assignees: list[int]
    assignees: list[int]
    earliest_start: int
    latest_end: int
    estimate: int
    exclude: bool

@dataclass
class SchedulerAssignment:
    id: int # task_id
    start_date: int
    end_date: int
    assignee: int

@dataclass
class Decoration:
    critical: bool

@dataclass
class InputTask:
    name: str
    description: str
    # This _should_ be string ( not Person ) 
    # since it doesn't contain any allocation information
    specific_assignments: bool
    assignees: list[str]
    next: list[str]
    parallelizable: bool
    estimate: Optional[int]
    start_date: Optional[date]
    end_date: Optional[date]
    status: Status
    input_row_idx: int

    # Added and edited by scheduler
    scheduler_fields: SchedulerFields = field(default_factory=lambda: SchedulerFields(0, [], [], 0, 0, 0, True))

    def __hash__(self):
        return hash(self.name)

@dataclass
class Team:
    name: str
    members: list[Person]

class Metadata:
    teams: dict[str, Team] = dict()
    people_allocations: dict[Person, float] = dict()

    # Add the person, only add the allocation if new 
    def add_person(self, person: Person):
        if person not in self.people_allocations:
            self.people_allocations[person] = 1.0
    
    # Add the person, then add the allocation, always override
    def add_allocation(self, person: Person, allocation: float):
        self.add_person(person)
        self.people_allocations[person] = allocation

    def add_team(self, team: Team):
        for m in team.members:
            self.add_person(m)
        self.teams[team.name] = team


