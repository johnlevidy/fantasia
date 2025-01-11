from .notification import Notification, Severity
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
        return None

    headers = data[0]
    if 'next' not in headers:
        notifications.append(Notification(Severity.ERROR, "Could not find 'next' column"))
        return None

    # We assume everything to the right of this column is a dependency
    next_index = headers.index('next')
    
    # Process each data row according to identified headers
    processed_data = []
    dropped_rows = 0 
    for row in data[1:]:
        # General case before the next_index
        row_dict = {k: v.strip() for k, v in zip(headers[:next_index], row[:next_index])}
        # Special case next_index and rightward
        row_dict['next'] = [v.strip() for v in row[next_index:] if v.strip()]
        # TODO: enforce invariants on data presence more generally ( json included )
        if not row_dict['Task']:
            dropped_rows += 1
            continue
        processed_data.append(row_dict)

    if dropped_rows:
        notifications.append(Notification(Severity.INFO, f"{dropped_rows} rows were dropped due to missing content"))
    return processed_data

def try_csv(data, notifications, delimiter):
    try:
        parsed = csv_string_to_data(data, notifications, delimiter=delimiter)
        return parsed
    except Exception as e:
        notifications.append(Notification(Severity.ERROR, f"Invalid CSV (delimiter ASCII: {ord(delimiter)})"))
        return None

