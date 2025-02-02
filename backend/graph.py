from datetime import datetime
import numpy as np
import networkx as nx
from networkx import NetworkXNoCycle

from .notification import Notification, Severity
from .dateutil import busdays_between, compare_busdays, busdays_after

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
            d = task[date_name]
            if d is not None:
                if project_start_date is not None and d.startswith('+'):                    
                    return busdays_after(project_start_date, int(d)) # Relative date.
                else:
                    return datetime.strptime(d, "%Y-%m-%d").date() # Absolute date.

        # Does this task set a start date for the project?
        if task_name == 'Start':
            project_start_date = get_date('StartDate')
            continue # Skip this task.

        # The estimate for this task.
        # TODO allow strings like 1w, 2m etc.
        estimate = int(task['Estimate']) if 'Estimate' in task else 0

        # Add the node to the graph and set attributes from the task.
        G.add_node(task_name,
            id         = next_id,
            start_date = get_date('StartDate'),
            end_date   = get_date('EndDate'),
            estimate   = estimate,
            assignee   = task['Assignee'] if 'Assignee' in task else '?',
            desc       = task['Description'] if 'Description' in task else '?',
            status     = task['Status'] if 'Status' in task else 'unknown'
        )
        next_id += 1

        # Link edges to next tasks.
        for next_task in task['next']:
            # Note that doing it this way means we expect a sentinel milestone in every project, we 
            # should enforce that invariant ( TODO ). Those must have 0 estimate for this to work
            # This mostly lets us use networkx algos and save code
            if next_task in task_set:
                G.add_edge(task_name, next_task, weight = estimate)

    return G

# Label tasks.
def label_tasks(G: nx.Graph):
    # Today's date - tasks that contain this date are "active".
    # TODO should match the user's timezone.
    today = datetime.now().date()

    for task_name in G.nodes:
        task = G.nodes[task_name]
        task['busdays'] = busdays_between(task['start_date'], task['end_date'])
        task['active']  = task['start_date'] <= today <= task['end_date']
        task['late']    = task['end_date'] < today and task['status'] != 'completed'
        task['up_next'] = False # default; will set later when we walk the graph.

        # Tasks following in progress or blocked tasks that are not started are "up next".
        if task['status'] == 'in progress' or task['status'] == 'blocked':       
            for next_task in G.neighbors(task_name):
                if G.nodes[next_task]['status'] == 'not started':
                    G.nodes[next_task]['up_next'] = True
                    break                    

# Returns True if there are any bad start / end dates
def find_bad_start_end_dates(G: nx.Graph, notifications):
    threshold = 2
    to_return = False
    for task_name, task in G.nodes(data=True):
        if not task['start_date'] or not task['end_date']:
            notifications.append(Notification(Severity.INFO, f"Task [{task_name}] does not seem to have a valid start or end date"))
            to_return = True
            continue

        # If the estimate is larger than the number of business dates that the task spans, flag it.
        # TODO account for the number of people assigned to the task as well?
        difference = compare_busdays(task['start_date'], task['end_date'], task['estimate'])
        if difference > threshold:
            notifications.append(Notification(Severity.INFO, f"Item [{task_name}] has an estimate inconsistent with start ({task['start_date']}) and end ({task['end_date']}). [Estimate: {task['estimate']}, Difference: {difference}, Threshold: {threshold}]"))
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
    total_work = sum(task[1]['estimate'] for task in G.nodes(data=True))
    longest_path = nx.dag_longest_path_length(G)
    return total_work, longest_path

# Finds nodes that end after the next node starts.
def find_start_next_before_end(G: nx.Graph, notifications):
    to_return = False
    for node in G.nodes:
        current_end_date = G.nodes[node]['end_date']
        for successor in G.successors(node):
            successor_start_date = G.nodes[successor]['start_date']
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
    alert_date = busdays_after(today_date, buffer_days) # Calculate the alert date using the buffer
    for node, data in G.nodes(data=True):
        start_date = data['start_date']
        if start_date:
          status = G.nodes[node]['status']

          # Check if the start date is within the buffer period from today and status is not 'in progress'
          if start_date <= alert_date and (status != 'in progress' and status != 'completed'):
            notifications.append(Notification(Severity.INFO, f"Node {node} starts on {start_date}, which is within {buffer_days} business days from today ({today_date}). Status: {status}. Check readiness."))

def compute_graph_metrics(parsed_content, notifications):
    # Check for cycles before running graph algorithms
    G = build_graph(parsed_content)
    print(G.nodes(data=True))

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

    # Decorations.
    label_tasks(G)

    # dont bother computing more metrics if there wasn't much intention behind the estimates
    if bad_start_end_dates:
        notifications.append(Notification(Severity.INFO, "Bad start and end dates prevent computation of more advanced metrics and alerts. Stopping."))
        return G

    # Check if any items aren't started that must have been started.
    check_start_dates(G, notifications, 3, datetime.now().date())

    # All done.
    return G
