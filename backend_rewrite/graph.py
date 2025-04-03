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

# Take in the InputTask graph and merge it with assignments
# output by the scheduler
def merge_with_assignments(G: nx.DiGraph) -> None:
    id = 0
    for v in G:
        v.id = id
        id += 1
