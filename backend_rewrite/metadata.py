from typing import Tuple
from io import StringIO
import csv

from .types import Metadata, Team, Person

# Used elsewhere
def row_contains_metadata(row: list[str]) -> bool:
    if not row:
        return False
    return row[0].strip().startswith('%')

def validate_and_convert_float(input_str):
    value = float(input_str)
    if 0 <= value <= 1:
        return value
    else:
        raise ValueError(f"Bad allocation must be on [0, 1]: {input_str}")

def parse_allocation(row: list[str]) -> Tuple[Person, float]:
    assert(row[0] == '%ALLOCATION')
    person_name = row[1].strip()
    person_allocation = validate_and_convert_float(row[2].strip())
    return Person(person_name), person_allocation

# Given a csv row with a team definition, make a Team object
def parse_team(row: list[str]) -> Team:
    assert(row[0] == '%TEAM')
    if len(row) <= 1:
        raise Exception(f"Team declaration for appears empty")
    team_name = row[1].strip()
    members = [Person(r.strip()) for r in row[2:] if r.strip()]

    if len(members) <= 0:
        raise Exception(f"Team declaration for {team_name} appears empty")
    
    return Team(team_name, members)
   
# Extracct all metadata from the input
def extract_metadata(input: str, delimiter: str) -> Metadata:
    csv_file_like = StringIO(input)
    data = list(csv.reader(csv_file_like, delimiter=delimiter))
    m = Metadata()
    for row in data:
        row = [r.strip() for r in row]
        if not row_contains_metadata(row):
            continue
        match row[0]:
            case '%TEAM':
                m.add_team(parse_team(row))
            case '%ALLOCATION':
                m.add_allocation(*parse_allocation(row))

    return m
