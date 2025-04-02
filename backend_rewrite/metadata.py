from io import StringIO
import csv

from .types import Metadata, Team, parse_person

def row_contains_metadata(row: list[str]) -> bool:
    return row[0].startswith('%')

def parse_team(row: list[str]) -> Team:
    assert(row[0] == '%TEAM')
    team_name = row[1].strip()
    members = [parse_person(r.strip()) for r in row[2:] if r.strip()]

    if len(members) <= 0:
        raise Exception(f"Team declaration for {team_name} appears empty")
    
    return Team(team_name, members)
   
## Catch metadata rows that aren't parsed correctly!
def extract_metadata(input: str, delimiter: str) -> Metadata:
    csv_file_like = StringIO(input)
    data = list(csv.reader(csv_file_like, delimiter=delimiter))

    m = Metadata()
    for row in data[1:]:
        match row[0]:
            case '%TEAM':
                m.add_team(parse_team(row))

    return m
