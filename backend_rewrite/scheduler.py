from dataclasses import dataclass
import datetime
from datetime import date
from .dateutil import busdays_between, busdays_offset
from copy import deepcopy
from typing import Tuple, Dict, Optional
from bidict import bidict 

from .types import *
from .notification import *
from ortools.sat.python import cp_model
from networkx import DiGraph

# Register eligible or fixed assignments for a task
def assign_people_to_task(model: cp_model.CpModel, person_assignments: Dict[int, cp_model.IntVar], scheduler_fields: SchedulerFields, person_ids):
    id: int = scheduler_fields.id
    if len(person_ids) == 1:
        person_assignments[id] = model.NewConstant(person_ids[0])
    elif len(person_ids) > 1:
        person_assignments[id] = model.NewIntVarFromDomain(
            cp_model.Domain.FromValues(person_ids), f'person_{id}')
         
# Register the start end end and interval of a task
def register_task_start_end(model: cp_model.CpModel, scheduler_fields: SchedulerFields, horizon: int,
                            task_starts: Dict[int, cp_model.IntVar], task_ends: Dict[int, cp_model.IntVar]):
    id = scheduler_fields.id
    # Create a new start variable for this subtask
    start_var = model.NewIntVar(0, horizon, f'start_{id}')
    end_var = model.NewIntVar(0, horizon, f'end_{id}')
    
    task_starts[id] = start_var
    task_ends[id] = end_var

class ValidTasks:
    def __init__(self, tasks):
        self.tasks = tasks
        self._iterator = None

    def __iter__(self):
        self._iterator = iter(self.tasks) # Create an iterator over the tasks
        return self

    def __next__(self) -> InputTask:
        # Loop through the internal iterator
        assert self._iterator
        for task in self._iterator:
            if not task.scheduler_fields.exclude:
                return task
        raise StopIteration

# Find a valid schedule, return assignments
def schedule(G: DiGraph, metadata: Metadata, person_to_person_id: bidict[Person, int],
             horizon: int, ts_specific: Dict[InputTask, list[InputTask]], notifications: list[Notification])\
             -> Tuple[Dict[InputTask, SchedulerAssignment], int]:
    model: cp_model.CpModel = cp_model.CpModel()

    # Model Variables
    task_starts: Dict[int, cp_model.IntVar] = {}
    task_ends: Dict[int, cp_model.IntVar] = {}
    person_assignments: Dict[int, cp_model.IntVar] = {}

    # -------------------------------------------------------------
    # Build constraints around who may be assigned to certain tasks
    task: InputTask
    for task in ValidTasks(G):
        if not task.scheduler_fields.assignees:
            register_task_start_end(model, task.scheduler_fields, horizon,
                                    task_starts, task_ends)
            assign_people_to_task(model, person_assignments, task.scheduler_fields, task.scheduler_fields.eligible_assignees)
            continue
        if not task.specific_assignments:
            raise Exception(f"Something unexpected happened in scheduling task: {task}")
        register_task_start_end(model, task.scheduler_fields, horizon,
                                task_starts, task_ends)
        assign_people_to_task(model, person_assignments, task.scheduler_fields, task.scheduler_fields.assignees)

    # -------------------------------------------------------------
    # Build constraints around ensuring subtasks of multi-assignments
    # are worked on simultaneously
    for task in ValidTasks(G):
        for s in ts_specific.get(task, []):
            model.Add(task_starts[task.scheduler_fields.id] ==
                      task_starts[s.scheduler_fields.id])
            model.Add(task_ends[task.scheduler_fields.id] ==
                      task_ends[s.scheduler_fields.id])

    # Force all subtasks to match the first start / end
    # model.Add(starts[subtasks[0]] == starts[subtasks[i]])
    # model.Add(ends[subtasks[0]] == ends[subtasks[i]])

    # ---------------------------------------------------------------
    # Tasks must end before their "latest end" assigned date
    task: InputTask
    for task in ValidTasks(G):
        model.Add(task_ends[task.scheduler_fields.id] <= task.scheduler_fields.latest_end)
        model.Add(task_starts[task.scheduler_fields.id] >= task.scheduler_fields.earliest_start)

    # ---------------------------------------------------------------
    # Constrain that successor items start after the end of the deps
    task: InputTask
    for task in ValidTasks(G):
        for successor in G.successors(task):
            if successor.scheduler_fields.exclude:
                raise Exception(f"May not have task: {task.name} depending on {successor.name} when {task.name} is not done ( no end date ) but {successor.name} is")
            model.Add(task_starts[successor.scheduler_fields.id] >= task_ends[task.scheduler_fields.id])

    # ---------------------------------------------------------------
    # Constrain people to non-overlapping tasks
    person_weighted_durations = {}
    for person, person_id in person_to_person_id.items():
        person_intervals = []
        weighted_durations = []
        task: InputTask
        for task in ValidTasks(G):
            is_assigned = model.NewBoolVar(f'assigned_{task.scheduler_fields.id}_to_{person_id}')
            # Although it'd be less ergonomic to retrive results later, I strongly
            # suspect it's possible to get rid of these variables, and person_assignments 
            # entirely . There's no additional info being provided by having person 
            # assignments to task ids vs. knowing whether or not somebody is assigned 
            # to a task. I tried for 5m and gave up
            model.Add(person_assignments[task.scheduler_fields.id] == person_id).OnlyEnforceIf(is_assigned)
            model.Add(person_assignments[task.scheduler_fields.id] != person_id).OnlyEnforceIf(is_assigned.Not())
            
            # These intervals may or may not exist, depending on whether or not 
            # the person is assigned. If they do, they cant overlap.
            optional_interval = model.NewOptionalIntervalVar(
                task_starts[task.scheduler_fields.id], task.scheduler_fields.estimate, task_ends[task.scheduler_fields.id], 
                is_assigned, f'opt_interval_{task.scheduler_fields.id}_{person_id}')
            person_intervals.append(optional_interval)

            weighted_duration = task.scheduler_fields.estimate * is_assigned
            weighted_durations.append(weighted_duration)
        
        model.AddNoOverlap(person_intervals)
        person_weighted_durations[person] = weighted_durations

    # ---------------------------------------------------------------
    # Define and Minimize the makespan
    makespan = model.NewIntVar(0, horizon, 'makespan')
    model.AddMaxEquality(makespan, [end for end in task_ends.values()])
    model.Minimize(makespan)

    # ---------------------------------------------------------------
    # Finally, ensure allocations are respected wrt the makespan
    for person in person_to_person_id.keys():
        a = metadata.people_allocations[person]
        if a != 1.0:
            model.Add(sum(person_weighted_durations[person]) * 100 <= int(a * 100) * makespan)

    # Solve the model
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 10

    status = solver.Solve(model)
    if status in [cp_model.INFEASIBLE]:
        print("Overconstrained")
        return dict(), -1
    elif status not in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        print("No solution found.")
        return dict(), -1
    status_str = "OPTIMAL" if status == cp_model.OPTIMAL else "FEASIBLE"
    s = f'Minimal makespan {status_str}: {solver.Value(makespan)} days\n'
    print(s)
    notifications.append(Notification(Severity.INFO, s))

    ret: Dict[InputTask, SchedulerAssignment] = dict()
    for task in ValidTasks(G):
        id = task.scheduler_fields.id
        start = solver.Value(task_starts[id])
        end = solver.Value(task_ends[id])
        assignee = solver.Value(person_assignments[id])
        ret[task] = SchedulerAssignment(id, start, end, assignee)

    return ret, solver.Value(makespan)
 
# Returns a pair of specific, eligible
def get_assignees(task: InputTask, metadata: Metadata, person_to_person_id: bidict[Person, int]) -> Tuple[list[int], list[int]]:
    # They are either all specific assignments or all team
    if not task.assignees:
        return [], [person_to_person_id[p] for p in metadata.people_allocations.keys()]
    if task.specific_assignments:
        return [person_to_person_id[Person(p)] for p in task.assignees], []
    pool: set[int] = set()
    for team in task.assignees:
        for p in metadata.teams[team].members:
            pool.add(person_to_person_id[p])

    return [], list(pool)

@dataclass
class DateResult:
    start_offset: int # Busdays from today until start
    end_offset: int # Busdays from today until end
    remaining_estimate: int # adjusted if today >= start / in progress

def densify_dates(task: InputTask, today: date, horizon: int) -> Optional[DateResult]:
    # If  the task ended in the past I do not care about it
    if task.end_date and today > task.end_date:
        return None

    in_progress = bool(task.start_date and today > task.start_date)

    match (in_progress, bool(task.start_date), bool(task.end_date), task.estimate is not None):
        # No estimate but may be derived
        case (_, True, True, False):
            effective_start = max(today, task.start_date) #type: ignore
            remaining_estimate = busdays_between(effective_start, task.end_date)
            return DateResult(busdays_between(today, effective_start), busdays_between(today, task.end_date), remaining_estimate)
        # No estimate and no way to derive it
        case (_, False, False, False):
            raise ValueError(f"Active or future task {task.name} has no way to infer estimate. Provide start + end or estimate")
        # I have an estimate and may or may not have a start or end
        # The task may have already begun or not
        # Future task which may or may not have start / end
        case (_, _, _, True):
            end = busdays_between(today, task.end_date) if task.end_date else horizon
            start = busdays_between(today, task.start_date) if task.start_date else 0
            already_complete = busdays_between(task.start_date, today) if task.start_date else 0
            assert task.estimate is not None
            return DateResult(start, end, task.estimate - already_complete)
        case (_, _, _, _):
            raise ValueError(f"Unexpected date layout for {task.name}: [{in_progress}, {task.start_date}, {task.end_date}, {task.estimate}]")

# 1. Expand assignees into eligible assignees
# 2. Assign unique people_id to Person
# 3. Assign unique task_id to task
# We need the subtasks mapping because specifically for the
# ones with multiple "specific" assignments we need to ensure
# they have the same start / end date
def find_solution(G: DiGraph, m: Metadata, ts_specific: Dict[InputTask, list[InputTask]], notifications: list[Notification]) -> Optional[int]:
    # Build dense Person / PersonId 
    person_to_person_id: bidict[Person, int] = bidict()
    task_to_task_id: bidict[InputTask, int] = bidict()

    # First we build the dense person identifiers
    id = 0
    for p in m.people_allocations.keys():
        person_to_person_id[p] = id
        id += 1
    horizon = sum([task.estimate for task in G])

    today: date = datetime.datetime.now().date()
    offset: int = 0
    # Expand assignees, densify dates and task_id

    id = 0
    today_offset = busdays_offset(today, -offset)
    task: InputTask
    for task in G:
        specific, pool = get_assignees(task, m, person_to_person_id)
        res: Optional[DateResult] = densify_dates(task, today, horizon)
        if not res:
            task.scheduler_fields = SchedulerFields(id, pool, specific, 0, horizon, 0, True)
        else:
            task.scheduler_fields = SchedulerFields(id, pool, specific, res.start_offset, res.end_offset, res.remaining_estimate, False)
        task_to_task_id[task] = id
        id += 1

    # At this point all scheduler fields are ready, we can attempt a solution no
    assignments, makespan = schedule(G, m, person_to_person_id, horizon, ts_specific, notifications)
    if assignments:
        # Apply the solution to the original graph
        # if we found one
        for task in ValidTasks(G):
            assignment: SchedulerAssignment = assignments[task]
            # If it's a parallelizable task we prefer to just display / present the original start constraint
            if not task.parallelizable or task.start_date is None:
                task.start_date = busdays_offset(today_offset, assignment.start_date)
            task.end_date = busdays_offset(today_offset, assignment.end_date)
            task.assignees = [person_to_person_id.inv[assignment.assignee].name]
        if offset != 0:
            notifications.append(Notification(Severity.WARN, f"Schedule only discovered by rolling back to {today_offset}"))
        return makespan
    return None
