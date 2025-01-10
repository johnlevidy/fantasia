import base64
import subprocess
import tempfile

from error import Error, Severity
from flask import Flask, request, jsonify, render_template
from json_parser import try_json
from csv_parser import try_csv
from graph import compute_dag_metrics
from dot import generate_dot_file

# TODO: Get rid of any throws, swallow and append to error_string, then return 
# those values and render in the table on the frontend

app = Flask(__name__, static_folder='../frontend/static', template_folder='../frontend/templates')

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/validate_json', methods=['POST'])
def validate_json():
    data = request.get_json()
    parsed_content = None
    error_string: list[Error] = []
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
        parallelism_ratio = total_length / critical_path_length

        notifications += [{"message": f"[Total Length: {total_length}], [Critical Path Length: {critical_path_length}], [Parallelism Ratio: {parallelism_ratio:.2f}]", "severity": "INFO"}]
        response = {
            "image": encoded_string,
            "notifications": notifications, 
        }
        return jsonify(response)
    
    except Exception as e:
        return jsonify({'message': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
