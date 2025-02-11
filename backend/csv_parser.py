from .dateutil import parse_date
from .notification import Notification, Severity
from .types import Metadata
from io import StringIO
import csv

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
    for row in data[1:]:
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
                [m.add_person(team, person.strip()) for person in row[2:] if person.strip()]
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

    return processed_data, m

def try_csv(data, notifications, delimiter):
    try:
        return csv_string_to_data(data, notifications, delimiter=delimiter)
    except Exception as e:
        notifications.append(Notification(Severity.ERROR, f"Invalid CSV (delimiter ASCII: {ord(delimiter)}) : {e}"))
        return None, None
