from io import StringIO
from graph import compute_dag_metrics
import base64
import subprocess
import csv
from flask import Flask, request, jsonify, render_template, send_file
import tempfile
from graphviz import Source
from dot import generate_dot_file
import json
import os

# TODO: Get rid of any throws, swallow and append to error_string, then return 
# those values and render in the table on the frontend

app = Flask(__name__, static_folder='../frontend/static', template_folder='../frontend/templates')

@app.route('/')
def home():
    return render_template('index.html')

def try_json(data, error_string):
    try:
        parsed_json = json.loads(data)
        return parsed_json
    except json.JSONDecodeError:
        error_string += ["Invalid JSON"]
    return None

def csv_string_to_data(csv_string, delimiter):
    csv_file_like = StringIO(csv_string)
    # Read the raw lines
    lines = csv_file_like.readlines()
    reader = csv.reader(lines, delimiter=delimiter)
    data = list(reader)
    print(data)
    if not data:
        return []

    # Extract headers
    headers = data[0]
    # Determine the 'next' column's starting index, assuming it exists
    if 'next' in headers:
        next_index = headers.index('next')
    else:
        raise ValueError("No 'next' column found in data")

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
        parsed = csv_string_to_data(data, delimiter=delimiter)
        # Continue processing if needed...
        # Example: Filtering entries with empty 'Task' or invalid rows
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

@app.route('/validate_json', methods=['POST'])
def validate_json():
    data = request.get_json()
    parsed_content = None
    error_string = []
    content = data['content']
    
    maybe_parsed_content = try_json(content, error_string)
    if maybe_parsed_content:
        print("JSON detected")
    if not maybe_parsed_content:
        maybe_parsed_content = try_csv(content, error_string, ',')
    if not maybe_parsed_content:
        maybe_parsed_content = try_csv(content, error_string, '\t')
    if not maybe_parsed_content:
        return jsonify({'message': str(error_string)}), 400
    
    try:
        dot_content = generate_dot_file(maybe_parsed_content)
        
        # Save dot_content to a temporary file
        with tempfile.NamedTemporaryFile(delete=False, mode='w', suffix='.dot') as dotfile:
            dotfile_path = dotfile.name
            dotfile.write(dot_content)

        # Define the output PNG file path
        output_png_path = dotfile_path + '.png'

        # Call Graphviz dot to render PNG
        subprocess.run(['dot', '-Tpng', dotfile_path, '-o', output_png_path], check=True)

        # Send the resulting PNG file
        with open(output_png_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
        notifications = []
        # TODO: Other return values should use this pattern and load the table, but
        # probably not this one
        total_length, critical_path_length = compute_dag_metrics(maybe_parsed_content)
        parallelism_ratio = critical_path_length / total_length

        notifications += [{"message": f"[Total Length: {total_length}], [Critical Path Length: {critical_path_length}], [Parallism Ratio: {parallelism_ratio:.2f}]", "severity": "INFO"}]
        response = {
            "image": encoded_string,
            "notifications": notifications, 
        }
        return jsonify(response)
    
    except Exception as e:
        return jsonify({'message': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
