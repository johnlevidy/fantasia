import base64
import subprocess
import tempfile

import html
import textwrap
import datetime
from collections import defaultdict

def generate_dot_file(data):
    item_dict = {item['Task']: item for item in data}
    graph = defaultdict(list)
    estimates = {}
    for item in data:
        if item['Task'] not in graph:
            graph[item['Task']] = []
        if 'next' in item:
            for next_item in item['next']:
                graph[item['Task']].append(next_item)
        estimates[item['Task']] = item.get('estimate', 1)

    dot_file = 'digraph Items {\n'
    dot_file += 'rankdir=LR;\n'
    dot_file += 'node [shape=plaintext];\n'
    for item in data:
        # Handle bad names
        node_name = item['Task'].replace(' ', '_')
        title = item['Task']
        description_color = 'red' if item.get('Status') == 'blocked' else 'lightblue'
        wrapped_description = '<br/>'.join(textwrap.wrap(html.escape(item['Description']), width=70))
        estimate = item.get('estimate', '')
        status = item.get('Status', '')
        dot_file += f"\"{node_name}\" [label=<<table border='1' cellborder='1'><tr><td colspan='2'>{title}</td></tr><tr><td bgcolor='lightgreen'>{item['StartDate']}</td><td bgcolor='lightyellow'>{item['EndDate']}</td></tr><tr><td colspan='2'>{item['Assignee']}</td></tr><tr><td colspan='2' bgcolor='{description_color}'>{wrapped_description}</td></tr><tr><td>Estimate: {estimate}</td><td>Status: {status}</td></tr></table>>];\n"
        for next_item in item.get('next', []):
            next_node_name = next_item.replace(' ', '_')
            dot_file += f"\"{node_name}\" -> \"{next_node_name}\" [color=black];\n"
    dot_file += '}\n'
    return dot_file

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

