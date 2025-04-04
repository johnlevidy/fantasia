from .dateutil import parse_date
from .notification import Notification, Severity
from .types import Metadata
from io import StringIO
import csv

def validate_and_convert_float(input_str):
    value = float(input_str)
    if 0 <= value <= 1:
        return value
    else:
        raise ValueError(f"Bad allocation must be on [0, 1]: {input_str}")

def parse_person(person):
    allocation = person.strip().split(':')
    if len(allocation) == 1:
        return allocation[0], 1
    elif len(allocation) == 2:
        return allocation[0], validate_and_convert_float(allocation[1])
    else:
        raise Exception(f"Invalid allocation specification: {person}")

def csv_string_to_data(csv_string, notifications, delimiter):
    csv_file_like = StringIO(csv_string)
    # Read the raw lines
    lines = csv_file_like.readlines()
    reader = csv.reader(lines, delimiter=delimiter)
    data = list(reader)
    if not data or len(data) == 0:
        notifications.append(Notification(Severity.ERROR, "CSV appears empty"))
        return None, None

    headers = data[0]
    if 'Task' not in headers:
        notifications.append(Notification(Severity.ERROR, f"Could not find 'Task' column parsing as ordinal-separated: {ord(delimiter)}"))
        return None, None
    if 'next' not in headers:
        notifications.append(Notification(Severity.ERROR, f"Could not find 'next' column parsing as ordinal-separated: {ord(delimiter)}"))
        return None, None

    # We assume everything to the right of this column is a dependency
    next_index = headers.index('next')

    # Process each data row according to identified headers
    processed_data = []
    m = Metadata()
    for row_idx, row in enumerate(data[1:]):
        # Skip empty rows.
        if len(row) == 0:
            continue

        # Special case - metadata is in rows where the first character of the first entry is %.
        # Supported syntax:
        # %TEAM,<team name>,<person 1>,<person 2>,....
        # %START,start date
        # %END,end date
        # %MINSLACK,slack   - how many days to leave between tasks when scheduling.
        match row[0]:
            case '%TEAM':
                if len(row) < 3: raise Exception("Invalid %TEAM declaration; skipping")
                team = row[1].strip()
                for person in row[2:]:
                    if not person.strip():
                        continue
                    person, allocation = parse_person(person)
                    m.add_person(team, person, allocation)
                continue 
            case '%START':
                if len(row) < 2: raise Exception("Invalid %START declaration; skipping")
                m.start_date = parse_date(row[1])
                continue
            case '%END':
                if len(row) < 2: raise Exception("Invalid %END declaration; skipping")
                m.end_date = parse_date(row[1])
                continue
            case '%MINSLACK':
                if len(row) < 2: raise Exception("Invalid %MINSLACK declaration; skipping")
                m.min_slack = int(row[1])
                continue

        # General case before the next_index
        row_dict = {k: v.strip() for k, v in zip(headers[:next_index], row[:next_index])}
        # Special case next_index and rightward
        row_dict['next'] = [v.strip() for v in row[next_index:] if v.strip()]
        # TODO: enforce invariants on data presence more generally ( json included )
        # Skip rows without a task name or tasks called Task (assume that's a repeated header row).
        if not row_dict['Task'] or row_dict['Task'] == 'Task':
            continue
        processed_data.append(row_dict)
        m.task_to_input_row_idx[row_dict['Task']] = row_idx

    return processed_data, m

def try_csv(data, notifications, delimiter):
    try:
        return csv_string_to_data(data, notifications, delimiter=delimiter)
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        notifications.append(Notification(Severity.ERROR, f"Invalid CSV (delimiter ASCII: {ord(delimiter)}) : {e}"))
        return None, None
