from .types import Metadata, InputTask, parse_person

def verify(m: Metadata, tasks: list[InputTask]) -> None:
    for t in tasks:
        for a in t.assignees:
            p = parse_person(a)
            if p not in m.people:
                raise Exception(f"InputTask definition {t.name} contained assignee {p} who is not defined in a team. Known people: {m.people}")

