from collections import defaultdict
import networkx as nx
import traceback
from typing import Dict, Tuple
import uuid
from .dot import generate_svg_graph
from backend.app import parse_to_python
from flask import Flask, request, jsonify, render_template, session
from .notification import Notification

from .types import *
from .parse_csv import csv_string_to_task_list 
from .metadata import extract_metadata
from .verify import verify_inputs, verify_graph
from .scheduler import find_solution
from .graph import build_graph, merge_graphs, decorate_and_notify
from .expand import expand_specific_tasks, expand_parallelizable_tasks
import os

app = Flask(__name__, static_folder='../frontend/static', template_folder='../frontend/templates')

app.secret_key = os.environ.get("FLASK_SECRET_KEY")

# uuid -> semi structured view of the last plan
last_plan:  Dict[str, list[Tuple[str, str, str]]] = defaultdict()

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

# Converting to string now makes our life a bit easier later
def build_plan(G) -> list[Tuple[str, str, str]]:
    task_to_input_row_idx = {}
    for task in G:
        task_to_input_row_idx[task.name] = task.input_row_idx

    result = [None] * (max([a.input_row_idx for a in G]) * 2)
    for task in G:
        start_string = task.start_date.strftime('%Y-%m-%d') if task.start_date else ''
        end_string = task.end_date.strftime('%Y-%m-%d') if task.end_date else ''
        result[task_to_input_row_idx[task.name]] = (start_string, end_string, ','.join(task.assignees))

    return result

def build_graph_and_schedule(tasks: list[InputTask], metadata: Metadata, notifications: list[Notification]) -> Tuple[nx.DiGraph, Optional[int], int]:
    # Build the upper graph and verify it
    G = build_graph(tasks, metadata)
    verify_graph(G)

    # Expand the tasks into subtasks where appropriate
    tasks, specific_subtasks = expand_specific_tasks(tasks)
    tasks, parallelizable_subtasks = expand_parallelizable_tasks(tasks)
    
    # Build the lower graph and verify it
    L = build_graph(tasks, metadata)
    verify_graph(L)

    # Do the scheduling, note that this statefully updates L
    makespan, offset = find_solution(L, metadata, specific_subtasks, notifications)

    if makespan:
        # Merge L back onto G
        merge_graphs(G, L, specific_subtasks, parallelizable_subtasks)

    return G, makespan, offset

@app.route('/process', methods=['POST'])
def process():
    try:
        content = request.get_json()['content']
        notifications: list[Notification] = list()

        # Make the python data structure and extract metadata
        # then verify the inputs are consistent
        metadata = extract_metadata(content, '\t')
        tasks = csv_string_to_task_list(content, '\t', metadata)
        verify_inputs(metadata, tasks)
        
        G, makespan, _ = build_graph_and_schedule(tasks, metadata, notifications)
        last_plan[get_user_id()] = build_plan(G) if makespan and makespan >= 0 else []

        # Decorate G before rendering
        decorations: Dict[InputTask, Decoration] = decorate_and_notify(G, makespan, notifications)

        response = {
            "image": generate_svg_graph(G, decorations),
            "notifications": [n.to_dict() for n in notifications], 
        }
        return jsonify(response)

    except Exception as e:
        print(f"Caught exception {e}")
        print(traceback.format_exc())
        return jsonify({'message': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('FANTASIA_PORT', 5000)), debug=True)
