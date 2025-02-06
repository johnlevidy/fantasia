import base64
import subprocess
import tempfile

import textwrap
import html
from .graph import Attr

def title_format(title):
    return '<FONT POINT-SIZE="14">' + title + '</FONT>'

def style_text(text, **kwargs):
    italic = kwargs.get('italic', False)
    bold   = kwargs.get('bold', False)
    
    s = text
    if italic: s = f"<i>{s}</i>"
    if bold:   s = f"<b>{s}</b>"
    
    return s

def dot_task(task_name, task):
    wrap_desc      = '<br/>'.join(textwrap.wrap(html.escape(task[Attr.desc]), width=70))
    title          = title_format(style_text(task_name, bold = task[Attr.critical]))

    start_date     = style_text(task[Attr.start_date],  italic = task[Attr.gen_start])
    start_color    = 'lightgray' if task[Attr.gen_start] else 'white'

    floot = ''
    if task[Attr.floot] < 0:
        floot = f'({abs(task[Attr.floot])}d late)'
    elif task[Attr.floot] > 0:
        floot = f'({task[Attr.floot]}d)'
    end_date       = style_text(f'{task[Attr.end_date]} {floot}', italic = task[Attr.gen_end])
    end_color      = 'lightgray' if task[Attr.gen_end] else 'white'

    estimate       = style_text(f"{task[Attr.estimate]}d  ({task[Attr.buffer]}d buf)", italic = task[Attr.gen_estimate])
    estimate_color = 'lightgray' if task[Attr.gen_estimate] else 'white'

    border_width = 1
    border_color = 'black'
    if task[Attr.late]:
        border_width = 3
        border_color = 'red'
    elif task[Attr.active]:
        border_width = 3
        border_color = 'lightgreen'
    elif task[Attr.soon]:
        border_width = 3
        border_color = 'lightyellow'

    # Milestones are tasks with zero days estimated effort.
    if task[Attr.estimate] == 0:
        return (
            f"{task[Attr.id]} [label=<"
            f"<table border='1' cellborder='1' cellspacing='0'><tr><td>{title}</td></tr>"
            f"<tr><td bgcolor='{end_color}'>{end_date}</td></tr>"
            f"<tr><td>{wrap_desc}</td></tr></table>"
            f">];"
        )

    # A regular task.
    match task[Attr.status]:
        case 'done':
            return (
                f"{task[Attr.id]} [label=<"
                f"<table border='1' color='lightblue' cellborder='1' cellspacing='0'><tr><td color='black' bgcolor='lightblue'>{title} (done)</td></tr>"
                f"<tr><td color='black' bgcolor='{end_color}'>{end_date}</td></tr></table>"
                f">];"
            )
        case 'not started':
            return (
                f"{task[Attr.id]} [label=<"
                f"<table border='{border_width}' color='{border_color}' cellborder='1' cellspacing='0'><tr><td color='black' colspan='2'>{title}</td></tr>"
                f"<tr><td color='black' bgcolor='{start_color}'>{start_date}</td><td color='black' bgcolor='{end_color}'>{end_date}</td></tr>"
                f"<tr><td color='black'>{task[Attr.assignee]}</td><td color='black' bgcolor='{estimate_color}'>{estimate}</td></tr>"
                f"<tr><td color='black' colspan='2'>{wrap_desc}</td></tr></table>"
                f">];"
            )
        case _:
            status_color = 'red' if task[Attr.status] == 'blocked' else 'lightgreen' if task[Attr.status] == 'in progress' else 'white'
            return (
                f"{task[Attr.id]} [label=<"
                f"<table border='{border_width}' color='{border_color}' cellborder='1' cellspacing='0'><tr><td color='black' colspan='3' bgcolor='{status_color}'>{title}</td></tr>"
                f"<tr><td color='black' bgcolor='{start_color}'>{start_date}</td><td color='black' bgcolor='{status_color}'>{task[Attr.user_status]}</td><td color='black' bgcolor='{end_color}'>{end_date}</td></tr>"
                f"<tr><td color='black' colspan='2'>{task[Attr.assignee]}</td><td color='black' bgcolor='{estimate_color}'>{estimate}</td></tr>"
                f"<tr><td color='black' colspan='3'>{wrap_desc}</td></tr></table>"
                f">];"
            )

def generate_dot_file(G):
    # Graph top-level.
    dot_file = (
        'digraph Items {\n'
        'rankdir=TB;\n'
        'node [fontname="Calibri,sans-serif" fontsize="12pt" shape=plaintext];\n'
        'edge [fontname="Calibri,sans-serif" fontsize="10pt"];\n'
    )

    # Write out all task nodes.
    dot_file += '\n'.join([dot_task(task_name, task) for task_name, task in G.nodes(data=True)])

    # Add in the edges.
    for u, v, edge in G.edges(data=True):
        color = 'gray'
        width = 1
        label = ''
        if edge[Attr.critical]:
            color = 'black'
            width = 2        
        if edge[Attr.slack] > 0:
            label = f"+{edge[Attr.slack]}d"
        elif edge[Attr.slack] < 0:
            color = 'red'
            label = f"late {abs(edge[Attr.slack])}d"            
        dot_file += f"{G.nodes[u][Attr.id]} -> {G.nodes[v][Attr.id]} [color={color}, penwidth={width}, label=\"{label}\"];\n"

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
