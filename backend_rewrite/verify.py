from typing import Optional, Any
from .dateutil import compare_busdays 
import networkx as nx
from networkx import NetworkXNoCycle
from .types import Metadata, InputTask, Person, Status

def verify_inputs(m: Metadata, tasks: list[InputTask]) -> None:
    for t in tasks:
        for a in t.assignees:
            if Person(a) not in m.people_allocations and a not in m.teams:
                raise Exception(f"InputTask definition {t.name} contained assignee {a} who is not defined in a team. Known people: {m.people_allocations.keys()}")

def find_cycle(G: nx.Graph) -> Optional[Any]: 
    try:
        return nx.find_cycle(G)
    except NetworkXNoCycle:
        return None

def find_incomplete_ancestor(G: nx.DiGraph, task: InputTask) -> list[InputTask]:
    preds = G.predecessors(task)
    if not preds:
        return []
    ret = []
    for p in preds:
        if p.status != Status.Completed and p.status != Status.Milestone:
            ret.append(p)
        ret.extend(find_incomplete_ancestor(G, p))
    return ret

# Finds nodes that end after the next node starts.
def find_bad_dates(G: nx.DiGraph):
    for task in G.nodes:
        if task.estimate and task.estimate < 0:
            raise Exception(f"Got estimate: {task.estimate} -- expected positive value only")
        if task.start_date and task.end_date and task.start_date >= task.end_date and task.estimate > 0:
            raise Exception(f"Task '{task.name}' has an end date before its start date")
        if task.start_date and task.end_date and task.estimate and compare_busdays(task.start_date, task.end_date, task.estimate) > 1:
            raise Exception(f"Task '{task.name}' has an estimate {task.estimate} \
                            that cannot fit in [{task.start_date.strftime('%Y-%m-%d')},\
                                                {task.end_date.strftime('%Y-%m-%d')}]")
        if task.status == Status.InProgress:
            incomplete_ancestors = find_incomplete_ancestor(G, task)
            if incomplete_ancestors:
                raise Exception(f"Task '{task.name}' is in progress but has incomplete ancestors: {[a.name for a in incomplete_ancestors]}")
        for s in G.successors(task):
            if task.end_date and s.start_date and s.start_date < task.end_date:
                raise Exception(f"Task '{task.name}' has an end date after next task [{s}] start date")

def verify_graph(G: nx.DiGraph) -> None:
    cycle = find_cycle(G)
    if cycle:
        raise Exception(f"Cycle detected in graph at: {cycle}. Cannot compute graph metrics.")
    find_bad_dates(G)
