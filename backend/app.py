from io import StringIO
import csv
from flask import Flask, request, jsonify, render_template, send_file
import tempfile
from graphviz import Source
from dot import generate_dot_file
import json
import os

app = Flask(__name__, static_folder='../frontend/static', template_folder='../frontend/templates')

@app.route('/')
def home():
    return render_template('index.html')

def render_content(parsed_json):
    try:
        dot_content = generate_dot_file(parsed_json)
        src = Source(dot_content)
        with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmpfile: 
            file_path = tmpfile.name
            src.render(file_path, format='png', cleanup=True)
            response = send_file(file_path + '.png', mimetype='image/png')
            return response
    except Exception as e:
        return 

def try_json(data, error_string):
    try:
        parsed_json = json.loads(data)
        return parsed_json
    except json.JSONDecodeError:
        error_string += ["Invalid JSON"]
    return None
 
def csv_string_to_data(csv_string, delimiter):
    # Use StringIO to simulate a file-like object for the CSV string
    csv_file_like = StringIO(csv_string)
    reader = csv.DictReader(csv_file_like, delimiter=delimiter)
    return list(reader) 

def try_csv(data, error_string, delimiter):
    try:
        parsed = csv_string_to_data(data, delimiter=delimiter)
        before_len = len(parsed)
        # Filter out entries with empty 'Task' or 'id', and trim spaces
        parsed = [{k: v.strip() for k, v in p.items()} for p in parsed if p['Task'].strip() and p['id'].strip()]
        for p in parsed:
            p['next'] = p['next'].split('|') if 'next' in p and p['next'] else []
        after_len = len(parsed)
        if after_len != before_len:
            print(f"Before length: {before_len}. After length: {after_len}")
        return parsed
    except Exception as e:
        print(e)
        error_string += [f"Invalid CSV (delimiter ASCII: {ord(delimiter)})"]
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
        print(maybe_parsed_content)
    if not maybe_parsed_content:
        maybe_parsed_content = try_csv(content, error_string, ',')
        print("Comma separated values detected")
        print(maybe_parsed_content)
    if not maybe_parsed_content:
        maybe_parsed_content = try_csv(content, error_string, '\t')
        print("Tab separated values detected")
        print(maybe_parsed_content)

    if not maybe_parsed_content:
        return jsonify({'message': str(error_string)}), 400

    try:
        dot_content = generate_dot_file(maybe_parsed_content)
        src = Source(dot_content)
        with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmpfile: 
            file_path = tmpfile.name
            src.render(file_path, format='png', cleanup=True)
            response = send_file(file_path + '.png', mimetype='image/png')
            return response
    except Exception as e:
        return jsonify({'message': str("Unable to render corresponding graphviz")}), 200
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
