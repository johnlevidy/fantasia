from typing import Optional, Any
import networkx as nx
from networkx import NetworkXNoCycle
from .types import Metadata, InputTask, Person

def verify_inputs(m: Metadata, tasks: list[InputTask]) -> None:
    for t in tasks:
        for a in t.assignees:
            if Person(a) not in m.people:
                raise Exception(f"InputTask definition {t.name} contained assignee {p} who is not defined in a team. Known people: {m.people}")

def find_cycle(G: nx.Graph) -> Optional[Any]: 
    try:
        return nx.find_cycle(G)
    except NetworkXNoCycle:
        return None

def verify_graph(G: nx.Graph) -> None:
    cycle = find_cycle(G)
    if cycle:
        raise Exception(f"Cycle detected in graph at: {cycle}. Cannot compute graph metrics.")

