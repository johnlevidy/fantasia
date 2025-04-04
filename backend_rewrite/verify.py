from typing import Optional, Any
from .dateutil import compare_busdays 
import networkx as nx
from networkx import NetworkXNoCycle
from .types import Metadata, InputTask, Person

def verify_inputs(m: Metadata, tasks: list[InputTask]) -> None:
    for t in tasks:
        for a in t.assignees:
            if Person(a) not in m.people:
                raise Exception(f"InputTask definition {t.name} contained assignee {a} who is not defined in a team. Known people: {m.people}")

def find_cycle(G: nx.Graph) -> Optional[Any]: 
    try:
        return nx.find_cycle(G)
    except NetworkXNoCycle:
        return None

# Finds nodes that end after the next node starts.
def find_bad_dates(G: nx.DiGraph):
    for task in G.nodes:
        if not task.start_date or not task.end_date:
            continue
        if task.start_date >= task.end_date and task.estimate > 0:
            raise Exception(f"Task '{task.name}' has an end date before its start date")
        if compare_busdays(task.start_date, task.end_date, task.estimate) > 0:
            raise Exception(f"Task '{task.name}' has an estimate {task.estimate} \
                            that cannot fit in [{task.start_date.strftime('%Y-%m-%d')},\
                                                {task.end_date.strftime('%Y-%m-%d')}]")
        for s in G.successors(task):
            if task.end_date and s.start_date and s.start_date <= task.end_date:
                raise Exception(f"Task '{task.name}' has an end date after next task [{s}] start date")

def verify_graph(G: nx.DiGraph) -> None:
    cycle = find_cycle(G)
    if cycle:
        raise Exception(f"Cycle detected in graph at: {cycle}. Cannot compute graph metrics.")
    find_bad_dates(G)
