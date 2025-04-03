from datetime import date
from typing import Dict, Optional, Tuple
from .types import InputTask, parse_status, Metadata
from .metadata import row_contains_metadata
from .dateutil import parse_date
from io import StringIO
import csv

# returns parallelizable, estimate, start, end, 
def parse_dates_and_estimates(estimate: str, start_date: str, end_date: str) -> Tuple[bool, int, Optional[date], Optional[date]]:
    start = parse_date(start_date) if start_date else None
    end = parse_date(end_date) if end_date else None
    parallelizable = False
    if not estimate:
        raise Exception(f"Got bad estimate: {estimate}")

    if estimate[0] == '~':
        estimate = estimate[1:]
        parallelizable = True
    if not estimate.isdigit():
        raise Exception(f"Got estimate: {estimate} should look like a plain integer.")
    est = int(estimate)
    if parallelizable and est <= 1:
        raise Exception(f"Got estimate: {estimate} marked parallelizable. Should only parallelize if > day")
    return parallelizable, est, start, end

# Verifies the assignee list and returns whether 
# they're all specific assignments or all team assignments
def verify_assignees(assignees: list[str],
                     m: Metadata) -> bool:
    is_specific = [a not in m.teams for a in assignees]
    consistent = all(a == is_specific[0] for a in is_specific)
    if not consistent:
        raise Exception(f"Task with assignees: {assignees} mixes team and specific assignments")
    return is_specific[0] if is_specific else False

def csv_string_to_task_list(csv_string: str, delimiter: str, metadata: Metadata) -> list[InputTask]:
    csv_file_like = StringIO(csv_string)
    data = list(csv.reader(csv_file_like, delimiter=delimiter))

    # Sanity checks
    if not data or len(data) == 0:
        raise Exception(f"No data in csv string {csv_string}")
    headers = data[0]

    # TODO: get all expected
    expected_columns = ['Task', 'Description', 'Estimate', 'StartDate', 'EndDate', 'Status', 'Assignee', 'next']
    for e in expected_columns:
        if e not in headers:
            raise Exception(f"No header '{e}' in headers: {headers}")

    # Get the position of the "next" columns, which
    # always appear at the end
    next_index = headers.index('next')

    processed_data: list[InputTask] = []
    for row_idx, row in enumerate(data[1:]):
        # Skip empty rows or rows with metadata
        if not row or row_contains_metadata(row):
            continue

        # General case, get all key, values before the next_index
        # Special case next_index and rightward
        row_dict: Dict[str, str] = {}
        row_dict = {k: v.strip() for k, v in zip(headers[:next_index], row[:next_index])}
        if not row_dict['Task']:
            continue

        # Special cases / non string types
        next = [v.strip() for v in row[next_index:] if v.strip()]
        assignees = [a.strip() for a in row_dict['Assignee'].split(',') if a.strip()]
        parallelizable, est, start, end = parse_dates_and_estimates(row_dict['Estimate'], row_dict['StartDate'], row_dict['EndDate'])
        status = parse_status(row_dict['Status'])
        t = InputTask(row_dict['Task'], row_dict['Description'], verify_assignees(assignees, metadata), assignees, next, parallelizable, est, start, end, status, row_idx)

        # Add to the output
        processed_data.append(t)

    return processed_data
