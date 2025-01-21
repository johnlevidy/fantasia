from .notification import Notification, Severity
from .dateutil import busdays_between, compare_busdays
import networkx as nx

# Build a networkx graph out of the parsed content
def build_graph(tasks):
    G = nx.DiGraph()
    for task in tasks:
        task_name = task['Task']
        G.add_node(task_name, **task)
        for next_task in task['next']:
            # Note that doing it this way means we expect a sentinel milestone in every project, we 
            # should enforce that invariant ( TODO ). Those must have 0 estimate for this to work
            # This mostly lets us use networkx algos and save code
            G.add_edge(task_name, next_task, weight = int(task['Estimate']))
    return G

# Returns True if any edge where A -> B has an A end date
# after the B start date.
def find_overlapping_start_end_dates(G: nx.Graph, notifications):
    threshold = 0
    to_return = False
    for task_name, task in G.nodes(data=True):
        this_end = task['EndDate']
        for next_task in G.neighbors(task_name):
            next_start = G.nodes[next_task]['StartDate']
            difference = busdays_between(next_start, this_end)
            if difference > threshold:
                notifications.append(Notification(
                    Severity.INFO,
                    f"Item [{next_task}] has start date {next_start} and prerequisite [{task_name}] has end date {this_end}. [Difference: {difference}, Threshold: {threshold}]"
                ))
                to_return = True
    return to_return

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

# 
def find_start_next_before_end(G: nx.Graph, notifications):
    for node in G.nodes:
        current_end_date = G.nodes[node]['EndDate']
        for successor in G.successors(node):
            successor_start_date = G.nodes[successor]['StartDate']
            # Check if the start date of the successor is before the end date of the current node
            if busdays_between(successor_start_date, current_end_date) > 0:
                notifications.append(Notification(Severity.ERROR, f"Task [{node}] has an end date after next task [{successor}] start date"))

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

      # dont bother computing more metrics if there wasn't much intention behind the estimates
      if bad_start_end_dates:
          notifications.append(Notification(Severity.INFO, "Bad start and end dates prevent computation of more advanced metrics and alerts. Stopping."))
          return

      # Check if any items aren't started that must have been started.
      find_start_next_before_end(parsed_content, notifications)
