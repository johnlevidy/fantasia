from .notification import Notification, Severity
from flask import Flask, request, jsonify, render_template
from .json_parser import try_json
from .csv_parser import try_csv
from .graph import compute_dag_metrics, find_cycle, find_bad_start_end_dates, find_unstarted_items, compute_graph_metrics
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

@app.route('/process', methods=['POST'])
def process():
    data = request.get_json()
    parsed_content = None
    notifications: list[Notification] = []
    content = data['content']
    
    parsed_content, notifications = parse_to_python(content)
    
    try:
        verify_schema(parsed_content, notifications)
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
