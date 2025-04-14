from collections import defaultdict
from copy import deepcopy
import networkx as nx
import traceback
from .dateutil import busdays_offset
import datetime
from typing import Dict, Tuple
import uuid
from .dot import generate_svg_graph
from backend.app import parse_to_python
from flask import Flask, request, jsonify, render_template, session
from .notification import Notification, Severity

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
last_graph: Dict[str, nx.DiGraph] = defaultdict()
last_decorations: Dict[str, Dict[InputTask, Decoration]] = defaultdict()
last_descendants: Dict[str, list[int]] = defaultdict()

def get_user_id():
    if 'user_id' not in session:
        session['user_id'] = str(uuid.uuid4())
    return session['user_id']

@app.route('/')
def home():
    get_user_id()
    return render_template('index.html')

@app.route("/get-descendants", methods=["POST"])
def get_descendants():
    data = request.get_json()
    if not data.get("node").isdigit():
        return jsonify({"descendants": []}), 404
    target_id = int(data.get("node"))
    G = last_graph.get(get_user_id())
    if G is None:
        return jsonify({"descendants": []}), 404

    # Find the node in the graph where scheduler_fields.id == target_id
    target_node: Optional[InputTask] = None
    for node in G:
        if node.scheduler_fields.id == target_id:
            target_node = node
            break

    if not target_node:
        return jsonify({"descendants": []}), 404

    # Convert back to scheduler_fields.id
    descendant_ids = []
    descendant_ids.append(target_id)
    for node in nx.descendants(G, target_node):
        descendant_ids.append(node.scheduler_fields.id)

    print(f"Returning descendants: {descendant_ids}")
    last_descendants[get_user_id()] = descendant_ids
    return jsonify({"descendants": descendant_ids})

@app.route('/get-copy-text', methods=['GET'])
def get_copy_text():
    lp = build_plan(last_graph[get_user_id()])
    response = { "text": '\n'.join(['\t'.join(l) if l else "\t\t\t" for l in lp])}
    return jsonify(response)

# Converting to string now makes our life a bit easier later
def build_plan(G) -> list[Tuple[str, str, str]]:
    task_to_input_row_idx = {}
    for task in G:
        task_to_input_row_idx[task.name] = task.input_row_idx

    result = [None] * (max([a.input_row_idx for a in G]) * 2 + 1)
    for task in G:
        start_string = task.start_date.strftime('%Y-%m-%d') if task.start_date else ''
        end_string = task.end_date.strftime('%Y-%m-%d') if task.end_date else ''
        result[task_to_input_row_idx[task.name]] = (start_string, end_string, ','.join(task.assignees))

    return result

def build_graph_and_schedule(tasks: list[InputTask], metadata: Metadata, notifications: list[Notification], step: int = 5) -> Tuple[nx.DiGraph, Optional[int], int]:
    # Build the upper graph and verify it
    offset: int = 0
    G = nx.DiGraph()

    today = datetime.datetime.now().date()
    for offset in range(0, 80, step):
        attempt_tasks = deepcopy(tasks)
        today_offset = busdays_offset(today, -offset)

        G = build_graph(attempt_tasks, metadata)
        verify_graph(G)

        # Expand the tasks into subtasks where appropriate
        attempt_tasks, specific_subtasks = expand_specific_tasks(attempt_tasks)
        attempt_tasks, parallelizable_subtasks = expand_parallelizable_tasks(attempt_tasks, today_offset)
        
        # Build the lower graph and verify it
        L = build_graph(attempt_tasks, metadata)
        verify_graph(L)

        # Do the scheduling, note that this statefully updates L
        makespan = find_solution(L, metadata, specific_subtasks, notifications)

        if makespan:
            # Merge L back onto G
            merge_graphs(G, L, specific_subtasks, parallelizable_subtasks)
            return G, makespan, offset

    notifications.append(Notification(Severity.WARN, f"Unable to find a schedule after rolling back {offset}d"))
    return G, None, offset

@app.route('/clear-last-selected', methods=['POST'])
def clear_last_selectetd():
    ld = set(last_descendants[get_user_id()])

    G = last_graph[get_user_id()]
    for t in G:
        if t.scheduler_fields.id in ld:
            t.start_date = None
            t.end_date = None
            t.assignees = []
        text = "is in" if t in last_decorations[get_user_id()] else "is not in"
        print(f"{t.name} {text} last decorations")

    response = {
        "image": generate_svg_graph(G, last_decorations[get_user_id()]),
        "notifications": [], 
    }
    return jsonify(response)

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

        # Decorate G before rendering
        decorations: Dict[InputTask, Decoration] = decorate_and_notify(G, makespan, notifications)
        last_graph[get_user_id()] = deepcopy(G)
        last_decorations[get_user_id()] = deepcopy(decorations)

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
