from collections import defaultdict
from datetime import datetime, timedelta
import numpy as np
import networkx as nx
from networkx import NetworkXNoCycle

from .milp_solve import milp_schedule_graph
from .notification import Notification, Severity
from .dateutil import busdays_between, busdays_offset, compare_busdays, parse_date
from .types import Task, Edge, Metadata
from .scheduler import schedule_graph, no_op_scheduler, AssigningScheduler, GreedyLevelingScheduler

# "Config".
# Threshold for tasks starting 'soon'.
soon_threshold = 2

# Status normalization.
status_normalization = { 
    '':              'not started',
    'completed':     'done',
    'in review':     'in progress',
    'investigating': 'in progress',
    'on hold':       'in progress',
    'paused':        'in progress',
    'waiting':       'in progress'
}

# Build a networkx graph out of the parsed content
def build_graph(task_rows, metadata):
    tasks = {}
    edges = []
    for task_row in task_rows:
        # Get a field from the row, returning the default if it's missing or empty.
        def get_field(field, default):
            if not field in task_row or task_row[field] == '':
                return default
            return task_row[field].strip()

        # Utility to get dates for the task; allow offsets from the project start, if set.
        def get_date(date_name):
            d = get_field(date_name, None)
            if d is None:
                return None
            if metadata.start_date is not None and d.startswith('+'):
                return busdays_offset(metadata.start_date, int(d)) # Relative date.
            else:
                return parse_date(d) # Absolute date.

        # Allocate a new Task and fill in the basic fields.
        task_name = task_row['Task']
        task = Task(task_name)
        tasks[task_name] = task
        task.desc       = get_field('Description', '')

        # Start date, end date, and estimate.
        # TODO allow strings like 1w, 2m etc for the estimate.
        default_estimate = 5
        task.start_date  = get_date('StartDate')
        task.end_date    = get_date('EndDate')
        estimate         = get_field('Estimate', '')
        task.estimate    = None if estimate == '' else int(estimate) 
        if task.start_date is None and task.end_date is None:
            # No dates - default the estimate if there isn't one.
            if task.estimate is None:
                task.estimate     = default_estimate
                task.gen_estimate = True
        elif task.start_date is not None and task.end_date is not None:
            # Both dates set - set the estimate to the task span if needed.
            if task.estimate is None:
                task.estimate = busdays_between(task.start_date, task.end_date)
        else:
            # Only one date is set; set the other based on it and the estimate.
            if task.estimate is None:
                task.estimate     = default_estimate
                task.gen_estimate = True
            if task.start_date is None:
                task.start_date = busdays_offset(task.end_date, -task.estimate)
            if task.end_date is None:
                task.end_date = busdays_offset(task.start_date, task.estimate)

        # Status.
        task.user_status = get_field('Status', 'not started')
        task.status = status_normalization.get(task.user_status, task.user_status)

        # Assignees.
        if 'Assignee' in task_row:
            task.user_assigned = [a.strip() for a in get_field('Assignee', '').split(',') if len(a.strip()) > 0]

        # Store edges.
        for next_task in task_row['next']:
            edges.append((task_name, next_task))

    # Build the graph itself, first adding nodes, then edges.
    G = nx.DiGraph()
    for task in tasks.values():
        G.add_node(task)
    for u, v in edges:
        if u in tasks and v in tasks:
            G.add_edge(tasks[u], tasks[v], **{
                Edge.weight   : tasks[u].estimate,
                Edge.slack    : 0,
                Edge.critical : False
            })
        else:
            # TODO this edge points to an undefined Task; let the user know.
            pass

    return G

def calculate_jit_dates(G: nx.Graph):
    # Similar to the date propagation, but in this case we start with the last task and force
    # setting predecessor start dates so that the project (and every task within it) starts as 
    # late as possible while still hitting the final end dates.
    # Only works if all leaf tasks have end dates.
    for task in reversed(list(nx.topological_sort(G))):
        # If this task doesn't already have a JIT end date, set it to the current end date.
        # Then set the JIT start based on the estimate.
        if not task.jit_end:
            task.jit_end = task.end_date
        task.jit_start = busdays_offset(task.jit_end, -task.estimate)

        # Backpropagate the JIT start date to predecessor tasks.
        for pred in G.predecessors(task):
            if not pred.jit_end or (task.jit_start < pred.jit_end):
                pred.jit_end = task.jit_start

# Decorate tasks with some useful information.
def decorate_tasks(G: nx.Graph):
    # Today's date - tasks that contain this date are "active".
    # TODO should match the user's timezone.
    today = datetime.now().date()

    for task in G.nodes:
        task.busdays = busdays_between(task.start_date, task.end_date)
        task.floot   = busdays_between(task.end_date, task.jit_end)
        task.buffer  = task.busdays - task.estimate
        if task.start_date > today:
            task.soon = busdays_between(today, task.start_date) <= soon_threshold
        else:
            if today <= task.end_date:
                task.active = True
            else:
                task.late = True

        # Calculate slack between this task and all successor tasks.
        # Tasks following in progress or blocked tasks that are not started are "up next".
        live = task.status == 'in progress' or task.status == 'blocked'
        for succ in G.successors(task):
            G.edges[task, succ][Edge.slack] = busdays_between(task.end_date, succ.start_date)
            if live and succ.status == 'not started':
                succ.up_next = True

    # Tag the critical path.
    critical_path = nx.dag_longest_path(G)
    for task in critical_path:
        task.critical = True
    for edge in zip(critical_path, critical_path[1:]):
        G.edges[edge][Edge.critical] = True

# Returns True if there are any bad start / end dates
def find_bad_start_end_dates(G: nx.Graph, notifications):
    to_return = False
    for task in G.nodes:
        if not task.start_date or not task.end_date:
            notifications.append(Notification(Severity.INFO, f"Task [{task_name}] does not seem to have a valid start or end date"))
            to_return = True
            continue

        # If the estimate is larger than the number of business dates that the task spans, flag it.
        # TODO account for the number of people assigned to the task as well?
        difference = compare_busdays(task.start_date, task.end_date, task.estimate)
        if difference > soon_threshold:
            notifications.append(Notification(Severity.INFO, 
                f"Item [{task}] has an estimate inconsistent with start ({task.start_date}) and end ({task.end_date}). "
                f"[Estimate: {task.estimate}, Difference: {difference}, Threshold: {soon_threshold}]"))
            to_return = True
    return to_return

# Returns a cycle if it contains any
def find_cycle(G: nx.Graph): 
    try:
        return nx.find_cycle(G)
    except NetworkXNoCycle:
        None 

# Computes total work and the longest path
def compute_dag_metrics(G: nx.Graph):
    total_work = sum(task.estimate for task in G.nodes)
    longest_path = nx.dag_longest_path_length(G)
    return total_work, longest_path

# Finds nodes that end after the next node starts.
def find_start_next_before_end(G: nx.Graph, notifications):
    to_return = False
    for task in G.nodes:
        current_end_date = task.end_date
        for succ in G.successors(task):
            successor_start_date = succ.start_date
            # Check if the start date of the successor is before the end date of the current node
            if not successor_start_date:
                notifications.append(Notification(Severity.INFO, f"Task [{task}] does not seem to have a valid date"))
                to_return = True
                continue
            if not current_end_date:
                notifications.append(Notification(Severity.INFO, f"Task [{task}] does not seem to have a valid date"))
                to_return = True
                continue
            if busdays_between(successor_start_date, current_end_date) > 0:
                to_return = True
                notifications.append(Notification(Severity.ERROR, f"Task [{task}] has an end date after next task [{succ}] start date"))
    return to_return

# Assuming find_start_next_before_end and find_bad_start_end_dates both hold, then 
# this check is equivalent to the "deep check" of walking back from every milestonegraph.py
# and ensuring items are started as necessary.
def check_start_dates(G: nx.Graph, notifications: list[Notification], buffer_days: int, today_date: datetime.date):
    alert_date = busdays_offset(today_date, buffer_days) # Calculate the alert date using the buffer
    for task in G.nodes:
        start_date = task.start_date
        status = task.status

        # Check if the start date is within the buffer period from today and status is not 'in progress'
        if start_date <= alert_date and (status != 'in progress' and status != 'done'):
            notifications.append(Notification(Severity.INFO, f"Task {task} starts on {start_date}, which is within {buffer_days} business days from today ({today_date}). Status: {status}. Check readiness."))

def find_valid_schedule(G, metadata, start_date):
    current_date = start_date
    max_date = start_date - timedelta(weeks=24)

    while current_date >= max_date:
        ret, makespan = milp_schedule_graph(G, metadata, current_date)
        if makespan != -1:
            return ret, makespan, current_date
        # subtract 1 week and try again
        current_date -= timedelta(weeks=1)
    # If no valid schedule is found within max range, just return nothing
    return None, -1, None

def compute_graph_metrics(parsed_content, metadata, notifications):
    # The metadata may specify a start date, but if it doesn't, set it to today.
    if metadata.start_date is None:
        # TODO use the user's timezone.
        metadata.start_date = datetime.now().date()

    # Check for cycles before running graph algorithms
    G = build_graph(parsed_content, metadata)

    cycle = find_cycle(G)
    if cycle:
        notifications.append(Notification(Severity.ERROR, f"Cycle detected in graph at: {cycle}. Cannot compute graph metrics."))
        raise Exception("Can't build graph.")

    total_length, critical_path_length = compute_dag_metrics(G)
    parallelism_ratio = total_length / critical_path_length
    notifications.append(Notification(Severity.INFO, f"[Total Length: {total_length}], [Critical Path Length: {critical_path_length}], [Parallelism Ratio: {parallelism_ratio:.2f}]"))

    today = datetime.now().date()
    ret, makespan, valid_date = find_valid_schedule(G, metadata, today)
    if today != valid_date:
        notifications.append(Notification(Severity.ERROR, f"Schedule was discovered only by rolling back {today} to {valid_date}"))

    end_date = busdays_offset(valid_date, makespan)
    if makespan != -1:
        s = f"Valid schedule found with makespan: {makespan} on date: {valid_date} that ends on {end_date}"
        print(s)
        notifications.append(Notification(Severity.INFO, s))
    else:
        notifications.append(Notification(Severity.FATAL, "No valid schedule found within the last 6 months. Exiting."))
        raise Exception("No valid schedule found within the last 6 months. Reconsider constraints.")

    # Print out the schedule and count how many days (and task-days) each person is working.
    days_alloc  = defaultdict(int)
    tasks_alloc = defaultdict(int)

    for assignment in ret:
        days_alloc[assignment.person_name] += (assignment.end - assignment.start)
        tasks_alloc[assignment.person_name] += 1

    # Print out the number of days allocated per person.
    for person in sorted(days_alloc.keys()):
        percentage_days_worked = (days_alloc[person] / makespan) * 100
        if tasks_alloc[person] > days_alloc[person]:
            s = f"{person} - working {days_alloc[person]}d, overallocated by {tasks_alloc[person] - days_alloc[person]}d, {int(percentage_days_worked)}% utilization."
            notifications.append(Notification(Severity.INFO, s))
            print(s)
        else:
            s = f"{person} - working {days_alloc[person]}d, {int(percentage_days_worked)}% utilization."
            notifications.append(Notification(Severity.INFO, s))
            print(s)

    # Other dates and decorations.
    calculate_jit_dates(G)
    decorate_tasks(G)

    # Identify bad dates.
    bad_start_end_dates = find_bad_start_end_dates(G, notifications)
    bad_start_end_dates = bad_start_end_dates or find_start_next_before_end(G, notifications)

    assignments = []

    tmp = set()
    # Have to add back whateveer got pruned / what I don't have an assignment for
    # This is getting very messy and we desperately need to clean up these abstractions
    for r in ret:
        tmp.add(r.task_name)

    for i, r in enumerate(G):
        if r.name not in tmp:
            assignments.append((r.name, r.start_date.strftime('%Y-%m-%d'), r.end_date.strftime('%Y-%m-%d'), ','.join([a for a in r.user_assigned])))

    for assignment in ret:
        start_date = busdays_offset(valid_date, assignment.start).strftime('%Y-%m-%d')
        end_date = busdays_offset(valid_date, assignment.end).strftime('%Y-%m-%d')
        assignments.append((assignment.task_name, start_date, end_date, assignment.person_name))

    # dont bother computing more metrics if there wasn't much intention behind the estimates
    if bad_start_end_dates:
        notifications.append(Notification(Severity.INFO, "Bad start and end dates prevent computation of more advanced metrics and alerts. Stopping."))
        return G, assignments

    # Check if any items aren't started that must have been started.
    check_start_dates(G, notifications, 3, datetime.now().date())

    # All done.
    return G, assignments
