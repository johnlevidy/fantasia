from io import StringIO
import csv

def csv_string_to_data(csv_string, error_string, delimiter):
    csv_file_like = StringIO(csv_string)
    # Read the raw lines
    lines = csv_file_like.readlines()
    reader = csv.reader(lines, delimiter=delimiter)
    data = list(reader)
    if not data or len(data) == 0:
        error_string += ["CSV appears empty"]
        return None

    headers = data[0]
    if 'next' not in headers:
        error_string += ["Could not find 'next' column"]
        return None

    # We assume everything to the right of this column is a dependency
    next_index = headers.index('next')
    
    # Process each data row according to identified headers
    processed_data = []
    for row in data[1:]:
        # Combine all 'next' values
        row_dict = {headers[i]: row[i].strip() for i in range(len(headers)) if i < next_index}
        row_dict['next'] = [row[i].strip() for i in range(next_index, len(row)) if row[i].strip()]
        processed_data.append(row_dict)

    return processed_data

def try_csv(data, error_string, delimiter):
    try:
        parsed = csv_string_to_data(data, error_string, delimiter=delimiter)
        # Continue processing if needed...
        parsed = [p for p in parsed if p['Task']]
        before_len = len(data.splitlines()) - 1  # Excluding header
        after_len = len(parsed)
        if after_len != before_len:
            print(f"Before length: {before_len}, After length: {after_len}")

        return parsed
    except Exception as e:
        print(e)
        error_string.append(f"Invalid CSV (delimiter ASCII: {ord(delimiter)})")
        return None

