import dataclasses
import itertools
from ortools.sat.python import cp_model
import argparse

from datetime import datetime
from backend.dateutil import parse_date, busdays_between, busdays_offset

def assign_people_to_task(model, person_assignments, id, person_ids):
    if len(person_ids) == 1:
        person_assignments[id] = model.NewConstant(person_ids[0])
    elif len(person_ids) > 1:
        person_assignments[id] = model.NewIntVarFromDomain(
            cp_model.Domain.FromValues(person_ids), f'person_{id}')
     
def register_task_start_end(model, id, horizon, intervals, starts, ends, task, expanded_tasks):
    expanded_tasks[id] = task
    # Create a new start variable for this subtask
    start_var = model.NewIntVar(0, horizon, f'start_{id}')
    end_var = model.NewIntVar(0, horizon, f'end_{id}')
    interval_var = model.NewIntervalVar(start_var, task.estimate, end_var, f'interval_{id}')
    
    intervals[id] = interval_var
    starts[id] = start_var
    ends[id] = end_var

# Returns the original task id if it wasn't split, the first subtask if it was
# because for split tasks only subtasks get start / end
def get_effective_id(task_id, task_to_subtasks):
    return task_to_subtasks.get(task_id, [task_id])[0]

def milp_solve(G, tasks, person_to_person_id, task_to_id, person_id_to_person, id_to_task):
    model = cp_model.CpModel()
    horizon = sum(task.estimate for task in tasks.values())
    intervals = {}
    starts = {}
    ends = {}
    person_assignments = {}
    expanded_tasks = {}
    task_to_subtasks = {}
    subtask_id_to_task_id = {}
    
    # -------------------------------------------------------------
    # Build constraints around who may be assigned to certain tasks
    for task_id, task in tasks.items():
        # No assignments exist yet
        if not task.scheduler_assigned:
            allowed_person_ids = [person_to_person_id[person] for person in task.assignee_pool]
            register_task_start_end(model, task_id, horizon, intervals, starts, ends, task, expanded_tasks) 
            assign_people_to_task(model, person_assignments, task_id, allowed_person_ids)
            continue

        # N >= 1 assignments already exist
        subtasks = []
        for i, person in enumerate(task.scheduler_assigned):
            subtask_id = f"{task_id}_person_{i}"
            subtasks.append(subtask_id)
            subtask_id_to_task_id[subtask_id] = task_id
            register_task_start_end(model, subtask_id, horizon, intervals, starts, ends, task, expanded_tasks)
            assign_people_to_task(model, person_assignments, subtask_id, [person_to_person_id[person]])
            # Force all subtasks to match the first start / end
            model.Add(starts[subtasks[0]] == starts[subtasks[i]])
            model.Add(ends[subtasks[0]] == ends[subtasks[i]])
        
        # Store the mapping from original task to subtasks for use later
        task_to_subtasks[task_id] = subtasks
        
    # ---------------------------------------------------------------
    # Tasks must end before their "latest end" assigned date
    for task_id, task in expanded_tasks.items():
        if task.latest_end is not None:
            model.Add(ends[task_id] <= task.latest_end)
   
    # ---------------------------------------------------------------
    # Constrain that successor items start after the end of the deps
    for original_task_id, task in tasks.items():
        for successor in G.successors(task):
            pred_id = get_effective_id(original_task_id, task_to_subtasks)
            succ_id = get_effective_id(task_to_id[successor.name], task_to_subtasks)
            # Add the dependency constraint
            model.Add(starts[succ_id] >= ends[pred_id])

    # ---------------------------------------------------------------
    # Constrain people to non-overlapping tasks
    for person in person_to_person_id.values():
        person_intervals = []
        for task_id in intervals:  # Use all task IDs (original and subtasks)
            is_assigned = model.NewBoolVar(f'assigned_{task_id}_to_{person}')
            # Although it'd be less ergonomic to retrive results later, I strongly
            # suspect it's possible to get rid of these variables, and person_assignments 
            # entirely . There's no additional info being provided by having person 
            # assignments to task ids vs. knowing whether or not somebody is assigned 
            # to a task. I tried for 5m and gave up
            model.Add(person_assignments[task_id] == person).OnlyEnforceIf(is_assigned)
            model.Add(person_assignments[task_id] != person).OnlyEnforceIf(is_assigned.Not())
            
            # These intervals may or may not exist, depending on whether or not 
            # the person is assigned. If they do, they cant overlap.
            optional_interval = model.NewOptionalIntervalVar(
                starts[task_id], expanded_tasks[task_id].estimate, ends[task_id], 
                is_assigned, f'opt_interval_{task_id}_{person}')
            person_intervals.append(optional_interval)
        
        model.AddNoOverlap(person_intervals)
    
    # Minimize the makespan
    makespan = model.NewIntVar(0, horizon, 'makespan')
    model.AddMaxEquality(makespan, [ends[task_id] for task_id in intervals])
    model.Minimize(makespan)
    
    # Solve the model
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 10
    status = solver.Solve(model)

    @dataclasses.dataclass
    class Assignment:
        task: int
        task_name: str
        person: int
        start: int
        end: int
        person_name: str

    ret = []
    if status in [cp_model.INFEASIBLE]:
        print("Overconstrained")
        return [], -1
    elif status not in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        print("No solution found.")
        return [], -1

    ms = solver.Value(makespan)
    status_str = "OPTIMAL" if status == cp_model.OPTIMAL else "FEASIBLE"
    print(f'Minimal makespan {status_str}: {solver.Value(makespan)} weeks\n')
    
    processed_original_tasks = set()
    for task_id in starts.keys():
        # Find the original task ID if this is a subtask id
        original_task_id = subtask_id_to_task_id[task_id] if task_id in subtask_id_to_task_id else task_id
        if original_task_id in processed_original_tasks:
            continue
            
        # Get start and ends for this task_id ( note again start and end are not on original_task_id )
        start = solver.Value(starts[task_id])
        end = solver.Value(ends[task_id])
        assigned_person = solver.Value(person_assignments[task_id])
        ret.append(Assignment(original_task_id, id_to_task[original_task_id].name, assigned_person, start, end, person_id_to_person[assigned_person]))
        processed_original_tasks.add(task_id)
    
    return ret, ms
    
def milp_schedule_graph(G, metadata):
    # create mapping from task name to number
    id_to_task = dict()
    task_to_id = dict()

    all_people = set(metadata.people) 

    person_id_to_person = dict()
    person_to_person_id = dict()

    # ----------------------------------
    # Build assignee_pools for each task
    for v in G:
        if not v.user_assigned:
            v.assignee_pool = all_people
            continue
        # For each assignee I see, if it's a team, add the whole team to the pool
        assignee_pool = []
        for a in v.user_assigned:
            if a in metadata.teams.keys():
                assignee_pool.extend(metadata.teams[a])
            # We already built a pool but now see a concrete assigned resource. 
            # Not supported right now, to support this we should add a notion of 
            # # of people on a project to target
            if assignee_pool and a not in metadata.teams.keys():
                raise Exception(f"FATA: task {v.name} contains a mix of team assignments and user assignments. Not supported. {v.user_assigned}")
        # If I didn't build a pool, they must have all been direct assignments.
        # Accept them all immediately
        if not assignee_pool:
            v.scheduler_assigned = v.user_assigned
        # Note that this still works in the case of no team assignments
        v.assignee_pool = assignee_pool

    # Build dense identifiers for people and tasks
    # for use in the optimization solver
    for i, p in enumerate(all_people):
        person_id_to_person[i] = p
        person_to_person_id[p] = i
    for i, r in enumerate(G):
        id_to_task[i] = r
        task_to_id[r.name] = i
    today = datetime.now().date()

    # Build latest_end on each task
    for v in G:
        # get latest_end from end
        v.latest_end = None
        if v.end_date:
            if isinstance(v.end_date, int):
                v.latest_end = v.end_date
            else:
                v.latest_end = busdays_between(today, v.end_date)

    ret, ms = milp_solve(G, id_to_task, person_to_person_id, task_to_id, person_id_to_person, id_to_task)
    for r in ret:
        id_to_task[r.task].start_date = busdays_offset(today, r.start)
        id_to_task[r.task].end_date = busdays_offset(today, r.end)
        id_to_task[r.task].user_assigned.append(r.person_name)
    return ret, ms
