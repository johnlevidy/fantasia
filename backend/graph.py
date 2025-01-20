from datetime import datetime
import numpy as np
from .notification import Notification, Severity

def compare_busdays(start_date, end_date, estimate):
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    busdays = np.busday_count(start.date(), end.date())
    return estimate - busdays

# Returns True if there are any bad start / end dates
def find_bad_start_end_dates(parsed_content, notifications):
    threshold = 2
    to_return = False
    for row in parsed_content:
        print(row)
        difference = compare_busdays(row['StartDate'], row['EndDate'], int(row['Estimate']))
        if abs(difference) > threshold:
            task = row['Task']
            notifications.append(Notification(Severity.INFO, f"Item {task} has an estimate inconsistent with start ({row['StartDate']}) and end ({row['EndDate']}). Estimate: {row['Estimate']}, Difference: {difference}, Threshold: {threshold}"))
            to_return = to_return or True
    return to_return

def find_cycle(tasks, next_key='next'):
    # Build adjacency dict: { task_name -> [list_of_next_tasks] }
    graph = {}
    for t in tasks:
        task_name = t["Task"]
        graph[task_name] = t.get(next_key, [])

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

def compute_dag_metrics(tasks, next_key='next', estimate_key='Estimate'):
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
        if not task[next_key]:
            return 0
        # Return the longest path from me
        current_estimate = int(task[estimate_key])
        return current_estimate + max(longest_path_to_end(task_dict[n]) for n in task[next_key])

    # Total work is the sum of all estimates
    total_work = sum(int(task[estimate_key]) for task in tasks)
    # Longest path is longest path from any start node
    longest_path = max(longest_path_to_end(task) for task in tasks)

    return total_work, longest_path
