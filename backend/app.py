import base64
import subprocess
import tempfile

from .notification import Notification, Severity
from flask import Flask, request, jsonify, render_template
from .json_parser import try_json
from .csv_parser import try_csv
from .graph import compute_dag_metrics, find_cycle
from .dot import generate_dot_file

# TODO: Get rid of any throws, swallow and append to error_string, then return 
# those values and render in the table on the frontend
app = Flask(__name__, static_folder='../frontend/static', template_folder='../frontend/templates')

@app.route('/')
def home():
    return render_template('index.html')

# Returns a pair of the parsed content / python object and the notifications 
# generated
def parse_to_python(content):
    json_notifications = []
    maybe_parsed_content = try_json(content, json_notifications)
    if maybe_parsed_content:
        return maybe_parsed_content, json_notifications

    csv_notifications = []
    maybe_parsed_content = try_csv(content, csv_notifications, ',')
    if maybe_parsed_content:
        return maybe_parsed_content, csv_notifications

    tsv_notifications = []
    maybe_parsed_content = try_csv(content, tsv_notifications, '\t')
    if maybe_parsed_content:
        return maybe_parsed_content, tsv_notifications

    return None, json_notifications + csv_notifications + tsv_notifications


# Generate dot content and return b64 encoded representation
def generate_svg_graph(parsed_content):
    dot_content = generate_dot_file(parsed_content)
    
    # Save dot_content to a temporary file
    with tempfile.NamedTemporaryFile(delete=False, mode='w', suffix='.dot') as dotfile:
        dotfile_path = dotfile.name
        dotfile.write(dot_content)

    # Define the output PNG file path
    output_svg_path = dotfile_path + '.svg'
    # Call Graphviz dot to render PNG
    print(output_svg_path)
    subprocess.run(['dot', '-Tsvg', dotfile_path, '-o', output_svg_path], check=True)
    with open(output_svg_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')

def compute_graph_metrics(parsed_content, notifications):
    # Check for cycles before running graph algorithms
    cycle = find_cycle(parsed_content)
    if cycle:
        notifications.append(Notification(Severity.ERROR, f"Cycle detected in graph at: {cycle}. Cannot compute graph metrics."))
    else:
      total_length, critical_path_length = compute_dag_metrics(parsed_content)
      parallelism_ratio = total_length / critical_path_length
      notifications.append(Notification(Severity.INFO, f"[Total Length: {total_length}], [Critical Path Length: {critical_path_length}], [Parallelism Ratio: {parallelism_ratio:.2f}]"))

@app.route('/process', methods=['POST'])
def process():
    data = request.get_json()
    parsed_content = None
    notifications: list[Notification] = []
    content = data['content']
    
    parsed_content, notifications = parse_to_python(content)
    
    try:
        compute_graph_metrics(parsed_content, notifications)
        encoded_string = generate_svg_graph(parsed_content)
        response = {
            "image": encoded_string,
            "notifications": [n.to_dict() for n in notifications], 
        }
        return jsonify(response)
    
    except Exception as e:
        return jsonify({'message': str(e), 'notifications': [n.to_dict() for n in notifications] }), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
