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
