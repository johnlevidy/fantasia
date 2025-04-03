from typing import Dict
from dataclasses import dataclass
from datetime import datetime
import networkx as nx

from .dateutil import busdays_offset, parse_date
from .types import InputTask, Metadata, Edge

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
        else:
            # TODO this edge points to an undefined Task; let the user know.
            pass

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
