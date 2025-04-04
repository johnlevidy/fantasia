from dataclasses import dataclass
import datetime
from datetime import date
from .dateutil import busdays_between, busdays_offset
from copy import deepcopy
from typing import Tuple, Dict, Optional
from bidict import bidict 

from .types import Metadata, SchedulerAssignment, Person, InputTask, SchedulerFields
from ortools.sat.python import cp_model
from networkx import DiGraph

# Register eligible or fixed assignments for a task
def assign_people_to_task(model: cp_model.CpModel, person_assignments: Dict[int, cp_model.IntVar], task: InputTask, person_ids):
    id: int = task.scheduler_fields.id
    if len(person_ids) == 1:
        person_assignments[id] = model.NewConstant(person_ids[0])
    elif len(person_ids) > 1:
        person_assignments[id] = model.NewIntVarFromDomain(
            cp_model.Domain.FromValues(person_ids), f'person_{id}')
         
# Register the start end end and interval of a task
def register_task_start_end(model: cp_model.CpModel, task: InputTask, horizon: int, 
                            task_starts: Dict[int, cp_model.IntVar], task_ends: Dict[int, cp_model.IntVar]):
    id = task.scheduler_fields.id
    # Create a new start variable for this subtask
    start_var = model.NewIntVar(0, horizon, f'start_{id}')
    end_var = model.NewIntVar(0, horizon, f'end_{id}')
    
    task_starts[id] = start_var
    task_ends[id] = end_var

# Find a valid schedule, return assignments
def schedule(G: DiGraph, metadata: Metadata, person_to_person_id: bidict[Person, int],
             horizon: int, ts_specific: Dict[InputTask, list[InputTask]]) -> Dict[InputTask, SchedulerAssignment]:
    model: cp_model.CpModel = cp_model.CpModel()

    # Model Variables
    task_starts: Dict[int, cp_model.IntVar] = {}
    task_ends: Dict[int, cp_model.IntVar] = {}
    person_assignments: Dict[int, cp_model.IntVar] = {}

    # -------------------------------------------------------------
    # Build constraints around who may be assigned to certain tasks
    task: InputTask
    for task in G:
        if not task.scheduler_fields.assignees:
            register_task_start_end(model, task, horizon,
                                    task_starts, task_ends)
            assign_people_to_task(model, person_assignments, task, task.scheduler_fields.eligible_assignees)
            continue
        if not task.specific_assignments:
            raise Exception(f"Something unexpected happened in scheduling task: {task}")
        register_task_start_end(model, task, horizon,
                                task_starts, task_ends)
        assign_people_to_task(model, person_assignments, task, task.scheduler_fields.assignees)

    # -------------------------------------------------------------
    # Build constraints around ensuring subtasks of multi-assignments
    # are worked on simultaneously
    for task in G:
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
    for task in G:
        model.Add(task_ends[task.scheduler_fields.id] <= task.scheduler_fields.end_time)

    # ---------------------------------------------------------------
    # Constrain that successor items start after the end of the deps
    task: InputTask
    for task in G:
        for successor in G.successors(task):
            model.Add(task_starts[successor.scheduler_fields.id] >= task_ends[task.scheduler_fields.id])

    # ---------------------------------------------------------------
    # Constrain people to non-overlapping tasks
    person_weighted_durations = {}
    for person, person_id in person_to_person_id.items():
        person_intervals = []
        weighted_durations = []
        task: InputTask
        for task in G:
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
        return dict()
    elif status not in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        print("No solution found.")
        return dict()
    status_str = "OPTIMAL" if status == cp_model.OPTIMAL else "FEASIBLE"
    print(f'Minimal makespan {status_str}: {solver.Value(makespan)} days\n')

    ret: Dict[InputTask, SchedulerAssignment] = dict()
    for task in G:
        id = task.scheduler_fields.id
        start = solver.Value(task_starts[id])
        end = solver.Value(task_ends[id])
        assignee = solver.Value(person_assignments[id])
        ret[task] = SchedulerAssignment(id, start, end, assignee)

    return ret
 
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

def densify_dates(today: date, start: Optional[date], end: Optional[date], horizon: int) -> Tuple[int, int]:
    s = busdays_between(today, start) if start else 0
    e = busdays_between(today, end) if end else horizon
    return s, e

# 1. Expand assignees into eligible assignees
# 2. Assign unique people_id to Person
# 3. Assign unique task_id to task
# We need the subtasks mapping because specifically for the
# ones with multiple "specific" assignments we need to ensure
# they have the same start / end date
def find_solution(G: DiGraph, m: Metadata, ts_specific: Dict[InputTask, list[InputTask]]) -> None:
    # Build dense Person / PersonId 
    person_to_person_id: bidict[Person, int] = bidict()
    task_to_task_id: bidict[InputTask, int] = bidict()

    # First we build the dense person identifiers
    id = 0
    for p in m.people_allocations.keys():
        person_to_person_id[p] = id
        id += 1
    task: InputTask
    horizon = sum([task.estimate for task in G])

    # Expand assignees, densify dates and task_id
    id = 0
    today = datetime.datetime.now().date()
    for task in G:
        specific, pool = get_assignees(task, m, person_to_person_id)
        s, e = densify_dates(today, task.start_date, task.end_date, horizon)
        task.scheduler_fields = SchedulerFields(id, pool, specific, s, e, task.estimate)
        task_to_task_id[task] = id
        id += 1

    # At this point all scheduler fields are ready, we can attempt a solution no
    assignments: Dict[InputTask, SchedulerAssignment] = schedule(G, m, person_to_person_id, horizon, ts_specific)

    # Apply the solution to the original graph
    # if we found one
    for task in G:
        assignment: SchedulerAssignment = assignments[task]
        task.start_date = busdays_offset(today, assignment.start_date)
        task.end_date = busdays_offset(today, assignment.end_date)
        task.assignees = [person_to_person_id.inv[assignment.assignee].name]
