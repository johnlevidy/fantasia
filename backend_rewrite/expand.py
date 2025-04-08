from typing import Dict, Tuple
from copy import deepcopy
from backend_rewrite.types import InputTask

def expand_parallelizable_tasks(tasks: list[InputTask]) -> Tuple[list[InputTask], Dict[InputTask, list[InputTask]]]:
    # Handle assigning start and end dates properly in this case
    ret = []
    ret.extend(tasks)
    original_to_subtasks: Dict[InputTask, list[InputTask]] = dict()
    tasks_to_add = []

    for t in tasks:
        if t.parallelizable:
            print(f"Splitting parallel {t.name} with start {t.start_date} end {t.end_date}")
            original_to_subtasks[t] = []
            assert t.estimate and t.estimate >= 2
            original_estimate = t.estimate
            original_end = t.end_date

            # Keep the start date, break the end / estimate
            t.end_date = None
            t.estimate = 1
            original_next = t.next
            last_t = t
            id = 1

            for _ in range(original_estimate)[1:]:
                t_copy = deepcopy(t)
                t_copy.name = t_copy.name + f"_chain_{id}"
                t_copy.estimate = 1
                t_copy.start_date = None
                t_copy.end_date = None
                last_t.next = [t_copy.name]
                tasks_to_add.append(t_copy)
                last_t = t_copy
                original_to_subtasks[t].append(t_copy)
                id += 1
            
            last_t.end_date = original_end
            last_t.next = original_next

    ret.extend(tasks_to_add)
    return ret, original_to_subtasks


# Returns a new list of input tasks as well as a dict which
# maps tasks back to their parent task where applicable
def expand_specific_tasks(tasks: list[InputTask]) -> Tuple[list[InputTask], Dict[InputTask, list[InputTask]]]:
    ret = []
    ret.extend(tasks)
    tasks_to_add = []

    # task name to subtasks
    original_to_subtasks: Dict[InputTask, list[InputTask]] = dict()

    for t in tasks:
        original_assignees = t.assignees
        if t.specific_assignments and len(original_assignees) > 1:
            original_to_subtasks[t] = []
            # Update the base one to have n assignment of the first one
            t.assignees = [original_assignees[0]]
            # Add tasks spanning this time range for everyone else
            # It should be OK for them to not be connected, since
            # we did the dep-sensitive expansion first
            id = 1
            added = []
            for a in original_assignees[1:]:
                # For every assignment on this item, append another with the same start / end date.
                # No need to capture deps since the ordering is captured by the original
                t_copy = deepcopy(t)
                t_copy.name = t_copy.name + f"_specific_{id}"
                t_copy.assignees = [a]
                added.append(t_copy)
                original_to_subtasks[t].append(t_copy)
                id += 1
            tasks_to_add.extend(added)

    # Anything which had any of my expanded tasks as next should
    # include the new ones as well
    ret.extend(tasks_to_add) 
    for t in ret:
        for n in t.next:
            for s in original_to_subtasks.get(n, []):
                t.next.append(s.name)

    return ret, original_to_subtasks
