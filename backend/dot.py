import base64
import subprocess
import tempfile

import textwrap
import datetime
from collections import defaultdict

def dot_task(task_name, task):
    wrapped_description = '<br/>'.join(textwrap.wrap(task['desc'], width=70))

    # Milestones are tasks with zero days estimated effort.
    if task['estimate'] == 0:
        return (
            f"{task['id']} [label=<"
            f"<table border='1' cellborder='1'><tr><td>{task_name}</td></tr>"
            f"<tr><td bgcolor='lightgreen'>{task['start_date']}</td></tr>"
            f"<tr><td>{wrapped_description}</td></tr></table>"
            f">];"
        )

    # A regular task.
    match task['status']:
        case 'completed':
            return (
                f"{task['id']} [label=<"
                f"<table border='1' cellborder='1'><tr><td>{task_name} (done)</td></tr>"
                f"<tr><td bgcolor='lightgray'>{task['end_date']}</td></tr></table>"
                f">];"
            )
        case 'not started':
            up_next_state = '(up next)' if task['up_next'] else ''
            return (
                f"{task['id']} [label=<"
                f"<table border='1' cellborder='1'><tr><td colspan='2'>{task_name} {up_next_state}</td></tr>"
                f"<tr><td bgcolor='lightgreen'>{task['start_date']}</td><td>{task['end_date']}</td></tr>"
                f"<tr><td>{task['assignee']}</td><td>{task['estimate']}d est ({task['busdays']}d avail)</td></tr>"
                f"<tr><td colspan='2'>{wrapped_description}</td></tr></table>"
                f">];"
            )
        case _:
            name_color = 'red' if task['late'] else 'lightblue' if task['active'] else 'white'
            name_state = '(late)' if task['late'] else '(active)' if task['active'] else ''
            status_color = 'red' if task['status'] == 'blocked' else 'lightblue'
            return (
                f"{task['id']} [label=<"
                f"<table border='1' cellborder='1'><tr><td colspan='3' bgcolor='{name_color}'>{task_name} {name_state}</td></tr>"
                f"<tr><td bgcolor='lightgreen'>{task['start_date']}</td><td bgcolor='{status_color}'>{task['status']}</td><td bgcolor='lightyellow'>{task['end_date']}</td></tr>"
                f"<tr><td colspan='2'>{task['assignee']}</td><td>{task['estimate']}d est ({task['busdays']}d avail)</td></tr>"
                f"<tr><td colspan='3'>{wrapped_description}</td></tr></table>"
                f">];"
            )

def generate_dot_file(G):
    # Graph top-level.
    dot_file = (
        'digraph Items {\n'
        'rankdir=LR;\n'
        'node [fontname="Calibri" fontsize="12pt" shape=plaintext];\n'
    )

    # Write out all task nodes.
    dot_file += '\n'.join([dot_task(task_name, task) for task_name, task in G.nodes(data=True)])

    # Add in the edges.
    for u, v in G.edges:
        dot_file += f"{G.nodes[u]['id']} -> {G.nodes[v]['id']} [color=black];\n"

    # Finish up.
    dot_file += '}\n'
    return dot_file

# Generate dot content and return b64 encoded representation
def generate_svg_graph(G):
    dot_content = generate_dot_file(G)
    
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
