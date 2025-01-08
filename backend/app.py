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

@app.route('/validate_json', methods=['POST'])
def validate_json():
    data = request.get_json()
    try:
        parsed_json = json.loads(data['content'])
        dot_content = generate_dot_file(parsed_json)
        src = Source(dot_content)
        file_path = '/tmp/graph.png'  # Temporary file path
        print(f"Rendering json with content: {json.dumps(parsed_json, indent=4)}")
        with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmpfile: 
            file_path = tmpfile.name
            src.render(file_path, format='png', cleanup=True)
            response = send_file(file_path + '.png', mimetype='image/png')
            return response
    except json.JSONDecodeError:
        return jsonify({'message': 'Invalid JSON'})
    except Exception as e:
        return jsonify({'message': str(e)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
