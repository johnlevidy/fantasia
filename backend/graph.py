from enum import StrEnum, auto
from datetime import datetime
import numpy as np
import networkx as nx
from networkx import NetworkXNoCycle

from .notification import Notification, Severity
from .dateutil import busdays_between, compare_busdays, busdays_offset

# "Config".
# Threshold for tasks starting 'soon'.
soon_threshold = 2

# Graph node and edge attributes this package uses.
class Attr(StrEnum):
    id           = auto() # int; a unique id for the task.
    start_date   = auto() # date; the task start date.
    end_date     = auto() # date; the task end date.
    estimate     = auto() # int; an estimate of the task effort in days.
    gen_start    = auto() # bool; True if a start date was generated for this task.
    gen_end      = auto() # bool; True if an end date was generated for this task.
    gen_estimate = auto() # bool; True if an estimate was generated for this task.
    jit_start    = auto() # date; the date this task should start if we want to have minimal slack in the project.
    jit_end      = auto() # date; the date this task should end if we want to have minimal slack in the project.
    buffer       = auto() # int; the number of business days difference between the task's scheduled dates and the estimate.
    floot        = auto() # int; how many business days later the task can end without causing the overall project to end late.
                          # actually the term is "float" but, you know.
    slack        = auto() # int; the number of business days difference between the task's end date and the start of the next. Assigned to edges.
    assignee     = auto() # str; who's assigned to the task.
    desc         = auto() # str; a description of the task.
    status       = auto() # str; the task status. TODO should also be an enum.
    user_status  = auto() # str; what the user entered for a status.
    busdays      = auto() # int; the number of business days between the task start and end.
    active       = auto() # bool; if True, this task has started but hasn't reached its end date.
    late         = auto() # bool; if True, this task's end date has passed and it's not done.
    soon         = auto() # bool; if True, this task starts in the next few days.
    up_next      = auto() # bool; if True, this task immediately follows one in progress.
    critical     = auto() # bool; if True, this task (and edge) is on the critical path for the project.
    weight       = auto() # int; the weight of the edge, based on the ancestor task estimate.

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
def build_graph(tasks):
    # A task with a special name of "Start" may set a start date for the whole graph.
    # If set, we'll allow relative start and end dates (in the form "+N").
    project_start_date = None

    G = nx.DiGraph()
    task_set = set([t['Task'] for t in tasks])
    next_id = 0
    for task in tasks:
        task_name = task['Task']

        # Get dates for the task; allow offsets from the project start, if set.
        def get_date(date_name):
            if date_name in task:
                d = task[date_name].strip()
                if d == '':
                    return None
                elif project_start_date is not None and d.startswith('+'):
                    return busdays_offset(project_start_date, int(d)) # Relative date.
                else:
                    return datetime.strptime(d, "%Y-%m-%d").date() # Absolute date.
            else:
                return None

        # Does this task set a start date for the project?
        if task_name == 'Start':
            project_start_date = get_date('StartDate')
            continue # Skip this task.

        # The estimate for this task.
        # TODO allow strings like 1w, 2m etc.
        default_estimate = 5
        estimate = int(task['Estimate']) if 'Estimate' in task else None

        # Status.
        user_status = task['Status'] if 'Status' in task else 'not started'
        status = status_normalization.get(user_status, user_status)

        # Add the node to the graph and set attributes from the task.
        G.add_node(task_name, **{
            Attr.id           : next_id,
            Attr.start_date   : get_date('StartDate'),
            Attr.end_date     : get_date('EndDate'),
            Attr.gen_start    : False,   # default; will be set to True later if necessary.
            Attr.gen_end      : False,   # default; will be set to True later if necessary.
            Attr.estimate     : default_estimate if estimate is None else estimate,
            Attr.gen_estimate : estimate is None,
            Attr.assignee     : task['Assignee'] if 'Assignee' in task else '?',
            Attr.desc         : task['Description'] if 'Description' in task else '?',
            Attr.status       : status,
            Attr.user_status  : user_status,
            Attr.active       : False,
            Attr.late         : False,
            Attr.soon         : False,
            Attr.up_next      : False,
            Attr.critical     : False
        })
        next_id += 1

        # Link edges to next tasks.
        for next_task in task['next']:
            # Note that doing it this way means we expect a sentinel milestone in every project, we 
            # should enforce that invariant ( TODO ). Those must have 0 estimate for this to work
            # This mostly lets us use networkx algos and save code
            if next_task in task_set:
                G.add_edge(task_name, next_task, **{
                    Attr.weight   : estimate,
                    Attr.critical : False
                })

    return G

# Populate start and end dates for all tasks in the graph that don't already have them.
def populate_dates(G: nx.Graph):
    # We'll do this in a couple of steps. First, back propagate dates (so start dates can
    # be based on end date - estimate, and end dates can be based on start dates of
    # successor tasks). Then, forward propagate using today's date as a default start for
    # any tasks that don't have either start dates or ancestors. The forward step is 
    # guaranteed to set start/end dates for any tasks that don't already have them.

    # Step 1 - backwards propagation.
    topo = list(nx.topological_sort(G))
    for task_name in reversed(topo):
        task = G.nodes[task_name]

        # If this task doesn't have an end date, we can't set a start date, nor can
        # we reason about dates for ancestor tasks. Skip it.
        if task[Attr.end_date] is None:
            continue

        # If it doesn't have a start date, set it based on the estimate.
        if task[Attr.start_date] is None:
            task[Attr.start_date] = busdays_offset(task[Attr.end_date], -task[Attr.estimate])
            task[Attr.gen_start]  = True

        # Propagate dates through the graph. Tasks without an end date will be assigned one;
        # if the gen_end flag is already set on the task then the end date will be updated
        # to match the earliest start date of successor tasks.
        for pred_name in G.predecessors(task_name):
            pred = G.nodes[pred_name]
            if pred[Attr.end_date] is None or (pred[Attr.gen_end] and task[Attr.start_date] < pred[Attr.end_date]):
                pred[Attr.end_date] = task[Attr.start_date]
                pred[Attr.gen_end]  = True

    # Step 2 - forwards propagation.
    # Tasks without predecessors will default to today's date, since that's the earliest
    # they _could_ start, at this point.
    # TODO should match the user's timezone.
    project_start_date = datetime.now().date()

    for task_name in topo:
        task = G.nodes[task_name]

        # If this task doesn't have a start_date it must be because it's a root task; default
        # it to the project start date.
        if task[Attr.start_date] is None:
            task[Attr.start_date] = project_start_date
            task[Attr.gen_start]  = True

        # If the task doesn't have an end date, set it based on the estimate.
        if task[Attr.end_date] is None:
            task[Attr.end_date] = busdays_offset(task[Attr.start_date], task[Attr.estimate])
            task[Attr.gen_end]  = True

        for succ_name in G.successors(task_name):
            succ = G.nodes[succ_name]
            if succ[Attr.start_date] is None or (succ[Attr.gen_start] and task[Attr.end_date] > succ[Attr.start_date]):
                succ[Attr.start_date] = task[Attr.end_date]
                succ[Attr.gen_start]  = True

def calculate_jit_dates(G: nx.Graph):
    # Similar to the date propagation, but in this case we start with the last task and force
    # setting predecessor start dates so that the project (and every task within it) starts as 
    # late as possible while still hitting the final end dates.
    # Only works if all leaf tasks have end dates.
    for task_name in reversed(list(nx.topological_sort(G))):
        task = G.nodes[task_name]

        # If this task doesn't already have a JIT end date, set it to the current end date.
        # Then set the JIT start based on the estimate.
        if Attr.jit_end not in task:
            task[Attr.jit_end] = task[Attr.end_date]
        task[Attr.jit_start] = busdays_offset(task[Attr.jit_end], -task[Attr.estimate])

        # Backpropagate the JIT start date to predecessor tasks.
        for pred_name in G.predecessors(task_name):
            pred = G.nodes[pred_name]
            if Attr.jit_end not in pred or (task[Attr.jit_start] < pred[Attr.jit_end]):
                pred[Attr.jit_end] = task[Attr.jit_start]

# Decorate tasks with some useful information.
def decorate_tasks(G: nx.Graph):
    # Today's date - tasks that contain this date are "active".
    # TODO should match the user's timezone.
    today = datetime.now().date()

    for task_name, task in G.nodes(data=True):
        task[Attr.busdays] = busdays_between(task[Attr.start_date], task[Attr.end_date])
        task[Attr.floot]   = busdays_between(task[Attr.end_date], task[Attr.jit_end])
        task[Attr.buffer]  = task[Attr.busdays] - task[Attr.estimate]
        if task[Attr.start_date] > today:
            task[Attr.soon] = busdays_between(today, task[Attr.start_date]) <= soon_threshold
        else:
            if today <= task[Attr.end_date]:
                task[Attr.active] = True
            else:
                task[Attr.late] = True

        # Calculate slack between this task and all successor tasks.
        # Tasks following in progress or blocked tasks that are not started are "up next".
        live = task[Attr.status] == 'in progress' or task[Attr.status] == 'blocked'
        for succ_name in G.successors(task_name):
            succ = G.nodes[succ_name]
            G.edges[task_name, succ_name][Attr.slack] = busdays_between(task[Attr.end_date], succ[Attr.start_date])
            if live and succ[Attr.status] == 'not started':
                succ[Attr.up_next] = True

    # Tag the critical path.
    critical_path = nx.dag_longest_path(G)
    for task_name in critical_path:
        G.nodes[task_name][Attr.critical] = True
    for edge in zip(critical_path, critical_path[1:]):
        G.edges[edge][Attr.critical] = True

# Returns True if there are any bad start / end dates
def find_bad_start_end_dates(G: nx.Graph, notifications):
    to_return = False
    for task_name, task in G.nodes(data=True):
        if not task[Attr.start_date] or not task[Attr.end_date]:
            notifications.append(Notification(Severity.INFO, f"Task [{task_name}] does not seem to have a valid start or end date"))
            to_return = True
            continue

        # If the estimate is larger than the number of business dates that the task spans, flag it.
        # TODO account for the number of people assigned to the task as well?
        difference = compare_busdays(task[Attr.start_date], task[Attr.end_date], task[Attr.estimate])
        if difference > soon_threshold:
            notifications.append(Notification(Severity.INFO, 
                f"Item [{task_name}] has an estimate inconsistent with start ({task[Attr.start_date]}) and end ({task[Attr.end_date]}). "
                f"[Estimate: {task[Attr.estimate]}, Difference: {difference}, Threshold: {soon_threshold}]"))
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
    total_work = sum(task[1][Attr.estimate] for task in G.nodes(data=True))
    longest_path = nx.dag_longest_path_length(G)
    return total_work, longest_path

# Finds nodes that end after the next node starts.
def find_start_next_before_end(G: nx.Graph, notifications):
    to_return = False
    for node in G.nodes:
        current_end_date = G.nodes[node][Attr.end_date]
        for successor in G.successors(node):
            successor_start_date = G.nodes[successor][Attr.start_date]
            # Check if the start date of the successor is before the end date of the current node
            if not successor_start_date:
                notifications.append(Notification(Severity.INFO, f"Task [{node}] does not seem to have a valid date"))
                to_return = True
                continue
            if not current_end_date:
                notifications.append(Notification(Severity.INFO, f"Task [{node}] does not seem to have a valid date"))
                to_return = True
                continue
            if busdays_between(successor_start_date, current_end_date) > 0:
                to_return = True
                notifications.append(Notification(Severity.ERROR, f"Task [{node}] has an end date after next task [{successor}] start date"))
    return to_return

# Assuming find_start_next_before_end and find_bad_start_end_dates both hold, then 
# this check is equivalent to the "deep check" of walking back from every milestonegraph.py
# and ensuring items are started as necessary.
def check_start_dates(G: nx.Graph, notifications: list[Notification], buffer_days: int, today_date: datetime.date):
    alert_date = busdays_offset(today_date, buffer_days) # Calculate the alert date using the buffer
    for node, data in G.nodes(data=True):
        start_date = data[Attr.start_date]
        if start_date:
          status = G.nodes[node][Attr.status]

          # Check if the start date is within the buffer period from today and status is not 'in progress'
          if start_date <= alert_date and (status != 'in progress' and status != 'done'):
            notifications.append(Notification(Severity.INFO, f"Node {node} starts on {start_date}, which is within {buffer_days} business days from today ({today_date}). Status: {status}. Check readiness."))

def compute_graph_metrics(parsed_content, notifications):
    # Check for cycles before running graph algorithms
    G = build_graph(parsed_content)

    cycle = find_cycle(G)
    if cycle:
        notifications.append(Notification(Severity.ERROR, f"Cycle detected in graph at: {cycle}. Cannot compute graph metrics."))
        raise Exception("Can't build graph.")

    total_length, critical_path_length = compute_dag_metrics(G)
    parallelism_ratio = total_length / critical_path_length
    notifications.append(Notification(Severity.INFO, f"[Total Length: {total_length}], [Critical Path Length: {critical_path_length}], [Parallelism Ratio: {parallelism_ratio:.2f}]"))

    # Identify bad dates.
    bad_start_end_dates = find_bad_start_end_dates(G, notifications)
    bad_start_end_dates = bad_start_end_dates or find_start_next_before_end(G, notifications)

    # Dates and decorations.
    # Do dates first so the decorators have something to work with.
    populate_dates(G)
    calculate_jit_dates(G)
    decorate_tasks(G)

    # dont bother computing more metrics if there wasn't much intention behind the estimates
    if bad_start_end_dates:
        notifications.append(Notification(Severity.INFO, "Bad start and end dates prevent computation of more advanced metrics and alerts. Stopping."))
        return G

    # Check if any items aren't started that must have been started.
    check_start_dates(G, notifications, 3, datetime.now().date())

    # All done.
    return G
