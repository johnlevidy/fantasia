from collections import defaultdict
import uuid
from .dot import generate_svg_graph
from backend.app import parse_to_python
from flask import Flask, request, jsonify, render_template, session
from .notification import Notification

from backend_rewrite.graph_metrics import output_graph_metrics
from .parse_csv import csv_string_to_task_list 
from .metadata import extract_metadata
from .verify import verify_inputs, verify_graph
from .graph import build_graph, merge_with_assignments
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
        notifications: list[Notification] = []

        # Make the python data structure and extract metadata
        # then verify the inputs are consistent
        metadata = extract_metadata(content, '\t')
        tasks = csv_string_to_task_list(content, '\t')
        verify_inputs(metadata, tasks)

        # Build the upper graph and verify it
        G = build_graph(tasks, metadata)
        verify_graph(G)

        # Append notifications with some helpful metrics
        output_graph_metrics(G, notifications)

        # Do the scheduling, get the assignments
        # TODO

        # Take scheudler outputs and do final graph 
        # decoration before generating graph visualization
        merge_with_assignments(G)

        response = {
            "image": generate_svg_graph(G),
            "notifications": [n.to_dict() for n in notifications], 
        }
        return jsonify(response)

    except Exception as e:
        print(f"Caught exception {e}")
        return jsonify({'message': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
