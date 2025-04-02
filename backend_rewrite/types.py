from dataclasses import dataclass
from enum import Enum, StrEnum, auto
from datetime import datetime

# Edges only have dicts to store data; use a StrEnum to define the keys we use.
class Edge(StrEnum):
    weight   = auto()  # int; the weight of the edge, based on the ancestor task estimate.
    slack    = auto()  # int; the number of business days difference between the task's end date and the start of the next. Assigned to edges.
    critical = auto()  # bool; True if this edge is on the critical path.

@dataclass
class Person:
    name: str
    allocation: float

    def __hash__(self) -> int:
        return hash(self.name)

class Status(Enum):
    InProgress = 1
    Blocked = 2
    Milestone = 3
    Completed = 4
    NotStarted = 5

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

@dataclass
class InputTask:
    name: str
    # This _should_ be string ( not Person ) 
    # since it doesn't contain any allocation information
    assignees: list[str]
    next: list[str]
    estimate: int
    start_date: datetime
    end_date: datetime
    status: Status
    input_row_idx: int

    def __hash__(self):
        return hash(self.name)

def validate_and_convert_float(input_str):
    value = float(input_str)
    if 0 <= value <= 1:
        return value
    else:
        raise ValueError(f"Bad allocation must be on [0, 1]: {input_str}")

def parse_person(person, allow_allocation = True):
    pa = person.strip().split(':')
    if len(pa) == 1:
        return Person(pa[0], 1)
    elif len(pa) == 2 and allow_allocation:
        return Person(pa[0], validate_and_convert_float(pa[1]))
    else:
        raise Exception(f"Invalid allocation specification: {person}, allow_allocation: {allow_allocation}")
       
@dataclass 
class Team:
    name: str
    members: list[Person]

class Metadata:
    teams: list[Team] = []
    people: set[Person] = set()

    def add_person(self, person: Person):
        if person not in self.people:
            self.people.add(person)

    def add_team(self, team: Team):
        for m in team.members:
            self.add_person(m)
        self.teams.append(Team(team.name, team.members))
