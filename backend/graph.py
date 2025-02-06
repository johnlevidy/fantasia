from datetime import datetime
import numpy as np
import networkx as nx
from networkx import NetworkXNoCycle

from .notification import Notification, Severity
from .dateutil import busdays_between, busdays_offset, compare_busdays, parse_date
from .types import Task, Edge, Metadata

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

        # Start date, end date, and estimate. If we have at least one date and an estimate,
        # we can set the other date. We need an estimate, though, so default it if it's
        # not present.
        # TODO allow strings like 1w, 2m etc.
        default_estimate = 5
        estimate = get_field('Estimate', '')
        if estimate == '':
            task.estimate     = default_estimate
            task.gen_estimate = True
        else:
            task.estimate = int(estimate)

        task.start_date = get_date('StartDate')
        task.end_date   = get_date('EndDate')
        if task.start_date is None:
            if task.end_date is not None:
                task.start_date = busdays_offset(task.end_date, -task.estimate)
                task.gen_start  = True
        elif task.end_date is None:
            task.end_date = busdays_offset(task.start_date, task.estimate)
            task.gen_end  = True

        # Status.
        task.user_status = get_field('Status', 'not started')
        task.status = status_normalization.get(task.user_status, task.user_status)

        # Assignees.
        if 'Assignee' in task_row:
            task.assigned = [a.strip() for a in get_field('Assignee', '').split(',') if len(a.strip()) > 0]

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

# Populate start and end dates for all tasks in the graph that don't already have them.
def populate_dates(G, metadata):
    # We'll do this in a couple of steps. First, back propagate dates (so start dates can
    # be based on end date - estimate, and end dates can be based on start dates of
    # successor tasks). Then, forward propagate using today's date as a default start for
    # any tasks that don't have either start dates or ancestors. The forward step is 
    # guaranteed to set start/end dates for any tasks that don't already have them.

    # Step 1 - backwards propagation.
    topo = list(nx.topological_sort(G))
    for task in reversed(topo):
        # If this task doesn't have an end date, use the metadata end date, if there
        # is one. If there isn't, we can't reason about its dates nor dates for 
        # ancestor tasks, so we'll skip it.
        if task.end_date is None:
            if metadata.end_date is None:
                continue
            task.end_date = metadata.end_date
            task.gen_end  = True

        # If it doesn't have a start date, set it now based on the estimate.
        # Note - this is done here since the end date could have been set from 
        # a successor task; this sets start date based on end date being set as
        # a consequence of the above logic as well as the below.
        if task.start_date is None:
            task.start_date = busdays_offset(task.end_date, -task.estimate)
            task.gen_start  = True

        # Propagate dates through the graph. Tasks without an end date will be assigned one;
        # if the gen_end flag is already set on the task then the end date will be updated
        # to match the earliest start date of successor tasks.
        for pred in G.predecessors(task):
            if pred.end_date is None or (pred.gen_end and task.start_date < pred.end_date):
                pred.end_date = task.start_date
                pred.gen_end  = True

    # Step 2 - forwards propagation.
    # Tasks without predecessors will default to today's date, since that's the earliest
    # they _could_ start, at this point.
    # TODO should match the user's timezone.
    project_start_date = datetime.now().date()
    for task in topo:
        # If this task doesn't have a start_date it must be because it's a root task; default
        # it to the project start date.
        if task.start_date is None:
            task.start_date = project_start_date
            task.gen_start  = True

        # If the task doesn't have an end date, set it based on the estimate.
        if task.end_date is None:
            task.end_date = busdays_offset(task.start_date, task.estimate)
            task.gen_end  = True

        for succ in G.successors(task):
            if succ.start_date is None or (succ.gen_start and task.end_date > succ.start_date):
                succ.start_date = task.end_date
                succ.gen_start  = True

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

    # Dates and decorations.
    # Do dates first so the decorators have something to work with.
    populate_dates(G, metadata)
    calculate_jit_dates(G)
    decorate_tasks(G)

    # Identify bad dates.
    bad_start_end_dates = find_bad_start_end_dates(G, notifications)
    bad_start_end_dates = bad_start_end_dates or find_start_next_before_end(G, notifications)

    # dont bother computing more metrics if there wasn't much intention behind the estimates
    if bad_start_end_dates:
        notifications.append(Notification(Severity.INFO, "Bad start and end dates prevent computation of more advanced metrics and alerts. Stopping."))
        return G

    # Check if any items aren't started that must have been started.
    check_start_dates(G, notifications, 3, datetime.now().date())

    # All done.
    return G
