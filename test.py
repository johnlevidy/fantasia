from ortools.sat.python import cp_model

def solve(tasks, num_people):
    model = cp_model.CpModel()
    horizon = sum(task['estimate'] for task in tasks.values())

    intervals = {}
    starts = {}
    ends = {}
    person_assignments = {}

    for task_id, task in tasks.items():
        estimate = task['estimate']
        start_var = model.NewIntVar(0, horizon, f'start_{task_id}')
        end_var = model.NewIntVar(0, horizon, f'end_{task_id}')
        interval_var = model.NewIntervalVar(start_var, estimate, end_var, f'interval_{task_id}')

        intervals[task_id] = interval_var
        starts[task_id] = start_var
        ends[task_id] = end_var

        # Constrain the latest end date of the task by the provided end date
        if task.get('latest_end') is not None:
            model.Add(end_var <= task['latest_end'])

        # Assign tasks to people
        if task.get('assignee') is not None:
            person_assignments[task_id] = model.NewConstant(task['assignee'])
        else:
            person_assignments[task_id] = model.NewIntVar(0, num_people - 1, f'person_{task_id}')

    # Constrain that successor items start after the end of the deps
    for task_id, task in tasks.items():
        for successor in task['next']:
            model.Add(starts[successor] >= ends[task_id])

    # Constrain people to non-overlapping tasks
    for person in range(num_people):
        person_intervals = []
        for task_id in tasks:
            is_assigned = model.NewBoolVar(f'assigned_{task_id}_to_{person}')
            model.Add(person_assignments[task_id] == person).OnlyEnforceIf(is_assigned)
            model.Add(person_assignments[task_id] != person).OnlyEnforceIf(is_assigned.Not())

            optional_interval = model.NewOptionalIntervalVar(
                starts[task_id], tasks[task_id]['estimate'], ends[task_id], is_assigned, f'opt_interval_{task_id}_{person}')
            person_intervals.append(optional_interval)

        model.AddNoOverlap(person_intervals)

    # Minimize the makespan ( unclear if this is what we want long term )
    makespan = model.NewIntVar(0, horizon, 'makespan')
    model.AddMaxEquality(makespan, [ends[task_id] for task_id in tasks])
    model.Minimize(makespan)

    # Solve the model
    solver = cp_model.CpSolver()
    status = solver.Solve(model)

    if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        print(f'Minimal makespan: {solver.Value(makespan)} weeks\n')
        for task_id in sorted(tasks):
            assigned_person = solver.Value(person_assignments[task_id])
            start = solver.Value(starts[task_id])
            end = solver.Value(ends[task_id])
            print(f'Task {task_id}: Person {assigned_person + 1}, Start: week {start}, End: week {end}')
        return solver.Value(makespan)
    else:
        print("No solution found.")
        return -1

tasks = {
    1: {'estimate': 3, 'next': [2, 3], 'assignee': None, 'latest_end': None},
    2: {'estimate': 2, 'next': [4], 'assignee': 1, 'latest_end': None},
    3: {'estimate': 4, 'next': [4], 'assignee': None, 'latest_end': 8},
    4: {'estimate': 1, 'next': [], 'assignee': None, 'latest_end': None},
}
num_people = 2

assert solve(tasks, num_people) == 8

tasks = {
    1: {'estimate': 3, 'next': [2, 3], 'assignee': None, 'latest_end': None},
    2: {'estimate': 2, 'next': [4], 'assignee': 1, 'latest_end': None},
    3: {'estimate': 4, 'next': [4], 'assignee': 1, 'latest_end': 8},
    4: {'estimate': 1, 'next': [], 'assignee': 1, 'latest_end': None},
}
num_people = 2

assert solve(tasks, num_people) == 10

# Add a person but overconstrained assignees
tasks = {
    1: {'estimate': 3, 'next': [2, 3], 'assignee': None, 'latest_end': None},
    2: {'estimate': 2, 'next': [4], 'assignee': 1, 'latest_end': None},
    3: {'estimate': 4, 'next': [4], 'assignee': 1, 'latest_end': 8},
    4: {'estimate': 1, 'next': [], 'assignee': 1, 'latest_end': None},
}
num_people = 3

assert solve(tasks, num_people) == 10

# Overconstrained delivery for 3 with any number of people
tasks = {
    1: {'estimate': 3, 'next': [2, 3], 'assignee': None, 'latest_end': None},
    2: {'estimate': 2, 'next': [4], 'assignee': 1, 'latest_end': None},
    3: {'estimate': 4, 'next': [4], 'assignee': 1, 'latest_end': 6},
    4: {'estimate': 1, 'next': [], 'assignee': 1, 'latest_end': None},
}
num_people = 7

assert solve(tasks, num_people) == -1
