from collections import defaultdict
import uuid
from backend.app import parse_to_python
from flask import Flask, request, jsonify, render_template, session
from .parse_csv import csv_string_to_task_list 
from .metadata import extract_metadata
from .verify import verify
from .graph import build_graph
import os

app = Flask(__name__, static_folder='../frontend/static', template_folder='../frontend/templates')

app.secret_key = os.environ.get("FLASK_SECRET_KEY")

last_plan = defaultdict(list)

def get_user_id():
    if 'user_id' not in session:
        session['user_id'] = str(uuid.uuid4())
    return session['user_id']

@app.route('/')
def home():
    get_user_id()
    return render_template('index.html')

@app.route('/get-copy-text', methods=['GET'])
def get_copy_text():
    response = { "text": '\n'.join(['\t'.join(l) if l else "\t\t\t" for l in last_plan.get(get_user_id(), [])])}
    return jsonify(response)

# The user might have given us data with blank rows
# in their sheet ( or uninterpretable ones as a task )
# for aesthetic reasons or otherwise. This is to handle that case.
def merge_data_with_rows(data, task_to_input_row_idx):
    result = [None] * (max([a for a in task_to_input_row_idx.values()]) + 1)
    for assignment in data:
        task_name = assignment[0]
        result[task_to_input_row_idx[task_name]] = assignment[1:]
    return result

@app.route('/process', methods=['POST'])
def process():
    try:
        content = request.get_json()['content']
        # Make the python data structure and extract metadata
        metadata = extract_metadata(content, '\t')
        tasks = csv_string_to_task_list(content, '\t')

        # Some final basic data sanity checks
        verify(metadata, tasks)

        # Build the upper graph
        G = build_graph(tasks, metadata)
        import networkx as nx
        critical_path = nx.dag_longest_path(G)
        crit_length = 0
        for task in critical_path:
            crit_length += task.estimate
        print(f"Critical path is {critical_path}")
        print(f"Length is: {crit_length}")
        print(metadata.teams)
        print(metadata.people)

        return jsonify({'message': str(tasks)}), 500
    except Exception as e:
        return jsonify({'message': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
