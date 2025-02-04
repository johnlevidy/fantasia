import base64
import subprocess
import tempfile

import textwrap
import datetime
from collections import defaultdict
from .graph import Attr

def title_format(title):
    return '<FONT POINT-SIZE="14">' + title + '</FONT>'

def style_text(text, **kwargs):
    italic = kwargs.get('italic', False)
    if italic:
        return f"<i>{text}</i>"
    else:
        return text

def dot_task(task_name, task):
    wrapped_description = '<br/>'.join(textwrap.wrap(task[Attr.desc], width=70))

    title = title_format(task_name)
    # Milestones are tasks with zero days estimated effort.
    if task[Attr.estimate] == 0:
        return (
            f"{task[Attr.id]} [label=<"
            f"<table border='1' cellborder='1'><tr><td>{title}</td></tr>"
            f"<tr><td bgcolor='lightgreen'>{task[Attr.start_date]}</td></tr>"
            f"<tr><td>{wrapped_description}</td></tr></table>"
            f">];"
        )

    # A regular task.
    start_date = style_text(task[Attr.start_date],     italic = task[Attr.gen_start])
    end_date   = style_text(task[Attr.end_date],       italic = task[Attr.gen_end])
    estimate   = style_text(f"{task[Attr.estimate]}d", italic = task[Attr.gen_estimate])
    match task[Attr.status]:
        case 'completed':
            return (
                f"{task[Attr.id]} [label=<"
                f"<table border='1' cellborder='1'><tr><td>{title} (done)</td></tr>"
                f"<tr><td bgcolor='lightgray'>{end_date}</td></tr></table>"
                f">];"
            )
        case 'not started':
            up_next_state = '(up next)' if task[Attr.up_next] else ''
            return (
                f"{task[Attr.id]} [label=<"
                f"<table border='1' cellborder='1'><tr><td colspan='2'>{title} {up_next_state}</td></tr>"
                f"<tr><td bgcolor='lightgreen'>{start_date}</td><td>{end_date}</td></tr>"
                f"<tr><td>{task[Attr.assignee]}</td><td>{estimate} est ({task[Attr.busdays]}d avail)</td></tr>"
                f"<tr><td colspan='2'>{wrapped_description}</td></tr></table>"
                f">];"
            )
        case _:
            name_color = 'red' if task[Attr.late] else 'lightblue' if task[Attr.active] else 'white'
            name_state = '(late)' if task[Attr.late] else '(active)' if task[Attr.active] else ''
            status_color = 'red' if task[Attr.status] == 'blocked' else 'lightblue'
            return (
                f"{task[Attr.id]} [label=<"
                f"<table border='1' cellborder='1'><tr><td colspan='3' bgcolor='{name_color}'>{title} {name_state}</td></tr>"
                f"<tr><td bgcolor='lightgreen'>{start_date}</td><td bgcolor='{status_color}'>{task[Attr.status]}</td><td bgcolor='lightyellow'>{end_date}</td></tr>"
                f"<tr><td colspan='2'>{task[Attr.assignee]}</td><td>{estimate} est ({task[Attr.busdays]}d avail)</td></tr>"
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
        dot_file += f"{G.nodes[u][Attr.id]} -> {G.nodes[v][Attr.id]} [color=black];\n"
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
