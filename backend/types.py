from collections import defaultdict
import dataclasses
from enum import StrEnum, auto

@dataclasses.dataclass
class Assignment:
    task: int
    task_name: str
    person: int
    start: int
    end: int
    person_name: str

# Graph nodes are Tasks.
# Identity is defined by name only, so the program can freely change other data on the task.
class Task:
    # A unique internal number for Task instances.
    next_id = 1

    def __init__(self, name):
        self.id = Task.next_id
        Task.next_id += 1

        self.name         = name   # str; the name of the task, also acts as the instance identity.
        self.start_date   = None   # date; the task start date.
        self.end_date     = None   # date; the task end date.
        self.estimate     = None   # int; an estimate of the task effort in days. If the provided estimate exceeds end - start it'll be reduced.
        self.gen_start    = False  # bool; True if a start date was calculated for this task.
        self.gen_end      = False  # bool; True if an end date was calculated for this task.
        self.gen_estimate = False  # bool; True if an estimate was calculated for this task.
        self.jit_start    = None   # date; the date this task should start if we want to have minimal slack in the project.
        self.jit_end      = None   # date; the date this task should end if we want to have minimal slack in the project.
        self.buffer       = 0      # int; the number of business days difference between the task's scheduled dates and the estimate.
        self.floot        = 0      # int; how many business days later the task can end without causing the overall project to end late.
                                   # actually the term is "float" but, you know.
        self.user_assigned     = []     # [str]; people and teams assigned to the task.
        self.scheduler_assigned = []     # [str]; who ends up getting assigned to the task by the scheduler (if the task's been scheduled).
        self.assignee_pool     = []     # [str]; who is eligible for assignment
        self.contended    = False  # bool; if True, the resources assigned to this task are also working on other tasks (if the task's been scheduled).
        self.desc         = None   # str; a description of the task.
        self.status       = None   # str; the task status. TODO should also be an enum.
        self.user_status  = None   # str; what the user entered for a status.
        self.busdays      = 0      # int; the number of business days between the task start and end.
        self.active       = False  # bool; if True, this task has started but hasn't reached its end date.
        self.late         = False  # bool; if True, this task's end date has passed and it's not done.
        self.soon         = False  # bool; if True, this task starts in the next few days.
        self.up_next      = False  # bool; if True, this task immediately follows one in progress.
        self.critical     = False  # bool; if True, this task (and edge) is on the critical path for the project.
        self.latest_end   = 0      # End in busdays

    def __eq__(self, other):
        if not isinstance(other, Task):
            return False
        return self.name == other.name

    def __hash__(self):
        return hash(self.name)

    def __repr__(self):
        return self.name

# Edges only have dicts to store data; use a StrEnum to define the keys we use.
class Edge(StrEnum):
    weight   = auto()  # int; the weight of the edge, based on the ancestor task estimate.
    slack    = auto()  # int; the number of business days difference between the task's end date and the start of the next. Assigned to edges.
    critical = auto()  # bool; True if this edge is on the critical path.

# Store all information about a project outside of the task graph itself.
class Metadata:
    # The person who does all the tasks nobody else has been assigned to.
    ANON = "Anon"

    def __init__(self):
        self.start_date = None
        self.end_date   = None
        self.min_slack  = 0
        self.teams      = defaultdict(list)
        self.people     = {}
        self.names      = set(self.ANON)
        self.task_to_input_row_idx = {}
        self.people_allocation = {}

    def add_person(self, team, person, allocation):
        # Team and person can't be the same name.
        if team == person:
            raise Exception(f"Can't use {team} as a team name and person name")

        # If the team doesn't already exist make sure it has a unique name.
        if not team in self.teams:
            if team in self.names:
                raise Exception(f"The team name \"{team}\" has already been used by another team or person")
            self.people_allocation[person] = allocation
            self.names.add(team)

        # Add the person to the list and the reverse index, first making sure the name is unique.
        if person in self.names:
            raise Exception(f"The person name \"{person}\" has already been used by another team or person")
        self.teams[team].append(person)
        self.people[person] = team
        self.people_allocation[person] = allocation
        self.names.add(person)
