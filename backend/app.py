from flask import Flask, request, jsonify, render_template
import traceback
from traceback import format_exc
from .notification import Notification, Severity
from .json_parser import try_json
from .csv_parser import try_csv
from .graph import compute_dag_metrics, compute_graph_metrics
from .dot import generate_dot_file, generate_svg_graph
from .schema import verify_schema

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
    maybe_parsed_content, metadata = try_json(content, json_notifications)
    if maybe_parsed_content:
        return maybe_parsed_content, metadata, json_notifications

    csv_notifications = []
    maybe_parsed_content, metadata = try_csv(content, csv_notifications, ',')
    if maybe_parsed_content:
        return maybe_parsed_content, metadata, csv_notifications

    tsv_notifications = []
    maybe_parsed_content, metadata = try_csv(content, tsv_notifications, '\t')
    if maybe_parsed_content:
        return maybe_parsed_content, metadata, tsv_notifications

    return None, None, json_notifications + csv_notifications + tsv_notifications

@app.route('/process', methods=['POST'])
def process():
    data = request.get_json()
    parsed_content = None
    notifications: list[Notification] = []
    content = data['content']
    
    parsed_content, metadata, notifications = parse_to_python(content)
    
    try:
        verify_schema(parsed_content, notifications)
        G = compute_graph_metrics(parsed_content, metadata, notifications)
        svg = generate_svg_graph(G)
        response = {
            "image": svg,
            "notifications": [n.to_dict() for n in notifications], 
        }
        return jsonify(response)
    
    except Exception as e:
        # For debugging convenience...
        print(f"Caught exception {e}")
        print(traceback.format_exc())
        # print(format_exc(e))


        # Let the client know.
        return jsonify({'message': str(e), 'notifications': [n.to_dict() for n in notifications] }), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
