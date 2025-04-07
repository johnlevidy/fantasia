from typing import Dict
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
import networkx as nx

from .notification import Notification, Severity

from .dateutil import busdays_between
from .types import InputTask, Metadata, Edge, Decoration, SOON_THRESHOLD

# Build a networkx graph out of the parsed content
def build_graph(task_list: list[InputTask], metadata: Metadata):
    tasks = {}
    edges = []
    for task in task_list:
        tasks[task.name] = task
        for next_task in task.next:
            edges.append((task.name, next_task))

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

    return G

def merge_parallel(task: InputTask, subtasks: list[InputTask]):
    # When recombining in parallel, this task start is necessarily
    # earliest, but I need to take the max end date of any and sum the
    # estimates
    combined_estimate = 1 + len(subtasks)

    # All end dates must be populated at this point if the scheduling succeeded
    combined_end_date = max([s.end_date for s in subtasks]) # type: ignore
    task.estimate = combined_estimate
    task.end_date = combined_end_date
    print(f"Merged estimate {combined_estimate} and end date {combined_end_date.strftime('%Y-%m-%d')}")

def merge_specific(task: InputTask, subtasks: list[InputTask]):
    # All have the same estimate, start, end, just merge assignments
    for s in subtasks:
        task.assignees.extend(s.assignees)

# Merge the lower graph ( expanded ) onto the upper graph
def merge_graphs(upper: nx.DiGraph, lower: nx.DiGraph,
                 ts_specific: Dict[InputTask, list[InputTask]], 
                 ts_parallelizable: Dict[InputTask, list[InputTask]]) -> None:
    # Iterate through the upper graph and "collect" all of the assignments in the lower graph
    # Do it in the reverse order they were expanded so we do ( parallel first )
    for task in upper:
        if task in ts_parallelizable:
            subtasks = ','.join([t.name for t in ts_parallelizable[task]])
            print(f"Merging a parallel task: {task.name} from [{subtasks}]")
            merge_parallel(task, ts_parallelizable[task])
    for task in upper:
        if task in ts_specific:
            subtasks = ','.join([t.name for t in ts_specific[task]])
            print(f"Merging a specific task: {task.name}. [{subtasks}]")
            merge_specific(task, ts_specific[task])

def decorate_and_notify(G: nx.DiGraph, notifications: list[Notification]) -> Dict[InputTask, Decoration]:
    ret: Dict[InputTask, Decoration] = dict()
 
    total_work = sum(task.estimate for task in G.nodes)
    longest_path = nx.dag_longest_path_length(G)
    parallelism_ratio = total_work / longest_path 
    notifications.append(Notification(Severity.INFO, f"[Total Length: {total_work}], [Critical Path Length: {longest_path}], [Parallelism Ratio: {parallelism_ratio:.2f}]"))

    # Prepare decorations, build days worked
    days_alloc  = defaultdict(int)
    today = datetime.now().date()

    task: InputTask
    for task in G:
        ret[task] = Decoration(False)
        for a in task.assignees:
            days_alloc[a] += task.estimate
        for succ in G.successors(task):
            if task.end_date and succ.start_date:
                G.edges[task, succ][Edge.slack] = busdays_between(task.end_date, succ.start_date)
        if task.start_date and busdays_between(today, task.start_date) <= SOON_THRESHOLD:
            notifications.append(Notification(Severity.INFO, f"Task {task.name} starts on {task.start_date}, which is within {SOON_THRESHOLD} business days from today. Status: {task.status}. Check readiness."))

    # Tag the critical path.
    critical_path = nx.dag_longest_path(G)
    makespan = 0
    for task in critical_path:
        ret[task].critical = True
        makespan += task.estimate
    for edge in zip(critical_path, critical_path[1:]):
        G.edges[edge][Edge.critical] = True
    
    # Provide some metrics on utilization
    for person in sorted(days_alloc.keys()):
        percentage_days_worked = (days_alloc[person] / makespan) * 100
        s = f"{person} - working {days_alloc[person]}d, {int(percentage_days_worked)}% utilization."
        notifications.append(Notification(Severity.INFO, s))
    return ret 
