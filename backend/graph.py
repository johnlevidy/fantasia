from datetime import datetime
import numpy as np
from .notification import Notification, Severity
import networkx as nx

def build_graph(tasks):
    G = nx.DiGraph()
    for task in tasks:
        task_name = task['Task']
        G.add_node(task_name, **task)
        for next_task in task['next']:
            G.add_edge(task_name, next_task)
    return G

def busdays_between(start_date, end_date):
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    return np.busday_count(start.date(), end.date())

def compare_busdays(start_date, end_date, estimate):
    return estimate - busdays_between(start_date, end_date)

def find_overlapping_start_end_dates(parsed_content, notifications):
    task_dict = {d['Task']: d for d in parsed_content}

    to_return = False
    for row in parsed_content:
        this_end = row['EndDate']
        for next in task_dict[row['Task']]['next']:
            next_start = task_dict[next]['StartDate']
            difference = busdays_between(next_start, this_end)
            if difference > 0:
                notifications.append(Notification(Severity.INFO, f"Item {task_dict[next]['Task']} has start date {next_start} and prerequisite {row['Task']} has end date {this_end}"))
                to_return = to_return or True
    return to_return

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

def find_cycle(tasks):
    # Build adjacency dict: { task_name -> [list_of_next_tasks] }
    graph = {}
    for t in tasks:
        task_name = t["Task"]
        graph[task_name] = t.get('next', [])

    visited = set()  # tasks that have been fully processed
    path = []        # current recursion stack as a list (to reconstruct path)
    in_stack = set() # same nodes as in path, but in a set for quick membership checks

    def dfs(current):
        """
        Perform DFS from 'current' task. Return a list of tasks forming a cycle
        if found; otherwise, return None.
        """
        visited.add(current)
        path.append(current)
        in_stack.add(current)

        for neighbor in graph.get(current, []):
            if neighbor not in visited:
                # DFS on the not-yet-visited neighbor
                cycle = dfs(neighbor)
                if cycle is not None:
                    return cycle  # If the neighbor found a cycle, bubble it up
            elif neighbor in in_stack:
                # We've encountered a task already in the current stack => cycle
                # Find where 'neighbor' first appeared in path to extract the cycle
                cycle_start_index = path.index(neighbor)
                # Return the cycle path, optionally repeat the first task to show closure
                return path[cycle_start_index:] + [neighbor]

        # Done exploring this path, remove current from the recursion stack
        path.pop()
        in_stack.remove(current)
        return None

    # Try DFS from each task
    for task_name in graph:
        if task_name not in visited:
            cycle = dfs(task_name)
            if cycle is not None:
                return cycle

    return None

def find_unstarted_items(tasks, notifications):
    # First, gather up milestones
    print(tasks)
    task_dict = {task['Task']: task for task in tasks}
    milestones = {task['Task']: task for task in tasks if task['Status'] == 'milestone'}

def compute_dag_metrics(tasks):
    # Map task IDs to task objects for quick access
    task_dict = {task['Task']: task for task in tasks}
    longest_path_cache = {}

    # Recursive function to compute the longest path to an end node
    def longest_path_to_end(task):
        task_id = task['Task']
        # If already computed, return the cached result
        if task_id in longest_path_cache:
            return longest_path_cache[task_id]
        # If I have no next, return current task estimate
        if not task['next']:
            return 0
        # Return the longest path from me
        current_estimate = int(task['Estimate'])
        return current_estimate + max(longest_path_to_end(task_dict[n]) for n in task['next'])

    # Total work is the sum of all estimates
    total_work = sum(int(task['Estimate']) for task in tasks)
    # Longest path is longest path from any start node
    longest_path = max(longest_path_to_end(task) for task in tasks)

    return total_work, longest_path

def compute_graph_metrics(parsed_content, notifications):
    # Check for cycles before running graph algorithms
    cycle = find_cycle(parsed_content)
    if cycle:
        notifications.append(Notification(Severity.ERROR, f"Cycle detected in graph at: {cycle}. Cannot compute graph metrics."))
    else:
      total_length, critical_path_length = compute_dag_metrics(parsed_content)
      parallelism_ratio = total_length / critical_path_length
      notifications.append(Notification(Severity.INFO, f"[Total Length: {total_length}], [Critical Path Length: {critical_path_length}], [Parallelism Ratio: {parallelism_ratio:.2f}]"))


      bad_start_end_dates = find_bad_start_end_dates(build_graph(parsed_content), notifications)

      # dont bother computing more metrics if there wasn't much intention behind the estimates
      if bad_start_end_dates:
          notifications.append(Notification(Severity.INFO, "Bad start and end dates prevent computation of more advanced metrics and alerts. Stopping."))
          return

      # Check if any items aren't started that must have been started.
      # find_unstarted_items(parsed_content, notifications)
