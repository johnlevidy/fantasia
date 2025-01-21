from datetime import datetime
import numpy as np

from .notification import Notification, Severity
from .dateutil import busdays_between, compare_busdays
import networkx as nx

# Build a networkx graph out of the parsed content
def build_graph(tasks):
    G = nx.DiGraph()
    task_set = set([t['Task'] for t in tasks])
    for task in tasks:
        task_name = task['Task']
        G.add_node(task_name, **task)
        for next_task in task['next']:
            # Note that doing it this way means we expect a sentinel milestone in every project, we 
            # should enforce that invariant ( TODO ). Those must have 0 estimate for this to work
            # This mostly lets us use networkx algos and save code
            if next_task in task_set:
                G.add_edge(task_name, next_task, weight = int(task['Estimate']))
    return G

# Returns True if there are any bad start / end dates
def find_bad_start_end_dates(G: nx.Graph, notifications):
    threshold = 2
    to_return = False
    for task_name, task in G.nodes(data=True):
        difference = compare_busdays(task['StartDate'], task['EndDate'], int(task['Estimate']))
        if abs(difference) > threshold:
            notifications.append(Notification(Severity.INFO, f"Item [{task_name}] has an estimate inconsistent with start ({task['StartDate']}) and end ({task['EndDate']}). [Estimate: {task['Estimate']}, Difference: {difference}, Threshold: {threshold}]"))
            to_return = to_return or True
    return to_return

# Returns a cycle if it contains any
def find_cycle(G: nx.Graph): 
    return nx.find_cycle(G)

# Computes total work and the longest path
def compute_dag_metrics(G: nx.Graph):
    total_work = sum(int(task[1]['Estimate']) for task in G.nodes(data=True))
    longest_path = nx.dag_longest_path_length(G)
    return total_work, longest_path

# Finds nodes that end after the next node starts.
def find_start_next_before_end(G: nx.Graph, notifications):
    to_return = False
    for node in G.nodes:
        current_end_date = G.nodes[node]['EndDate']
        for successor in G.successors(node):
            successor_start_date = G.nodes[successor]['StartDate']
            # Check if the start date of the successor is before the end date of the current node
            if busdays_between(successor_start_date, current_end_date) > 0:
                to_return = to_return or True
                notifications.append(Notification(Severity.ERROR, f"Task [{node}] has an end date after next task [{successor}] start date"))
    return to_return

# Assuming find_start_next_before_end and find_bad_start_end_dates both hold, then 
# this check is equivalent to the "deep check" of walking back from every milestonegraph.py
# and ensuring items are started as necessary.
def check_start_dates(G: nx.Graph, notifications: list[Notification], buffer_days: int, today_date: datetime.date):
    alert_date = np.busday_offset(today_date, buffer_days, roll='forward')  # Calculate the alert date using the buffer

    for node, data in G.nodes(data=True):
        print(node)
        print(data)
        start_date_str = data['StartDate']
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        status = G.nodes[node].get('Status', 'unknown')  # Assuming 'unknown' if status not set

        # Check if the start date is within the buffer period from today and status is not 'in progress'
        if start_date <= alert_date and (status != 'in progress' and status != 'completed'):
            notifications.append(Notification(Severity.INFO, f"Node {node} starts on {start_date}, which is within {buffer_days} business days from today ({today_date}). Status: {status}. Check readiness."))

def compute_graph_metrics(parsed_content, notifications):
    # Check for cycles before running graph algorithms
    G = build_graph(parsed_content)
    cycle = find_cycle(G)
    if cycle:
        notifications.append(Notification(Severity.ERROR, f"Cycle detected in graph at: {cycle}. Cannot compute graph metrics."))
    else:
      total_length, critical_path_length = compute_dag_metrics(parsed_content)
      parallelism_ratio = total_length / critical_path_length
      notifications.append(Notification(Severity.INFO, f"[Total Length: {total_length}], [Critical Path Length: {critical_path_length}], [Parallelism Ratio: {parallelism_ratio:.2f}]"))

      bad_start_end_dates = find_bad_start_end_dates(G, notifications)
      bad_start_end_dates = bad_start_end_dates or find_start_next_before_end(parsed_content, notifications)

      # dont bother computing more metrics if there wasn't much intention behind the estimates
      if bad_start_end_dates:
          notifications.append(Notification(Severity.INFO, "Bad start and end dates prevent computation of more advanced metrics and alerts. Stopping."))
          return

      # Check if any items aren't started that must have been started.
      check_start_dates(G, notifications, 3, datetime.now().date())
