import base64
from datetime import datetime
from typing import Dict
import subprocess
import tempfile
import os

from .dateutil import busdays_between
import textwrap
import html
from .types import *

def title_format(title):
    return '<FONT POINT-SIZE="14">' + title + '</FONT>'

def style_text(text, **kwargs):
    italic = kwargs.get('italic', False)
    bold   = kwargs.get('bold', False)
    
    s = text
    if italic: s = f"<i>{s}</i>"
    if bold:   s = f"<b>{s}</b>"
    
    return s

# Deprecated
# gen_start -- because it's always either provided or generated now, there's no 
# thing where it assigns an initial one then massages it. easy enough for user
# to deduce on their own i think?
# floot -- i'm not sure we can compute this anymore, knowing how many days late
# an item can be before the project is late requires accounting for that persons
# entire subgraph going forward ( and its relation to everyone elses ) -- I think 
# it just degenerates into another full optimization?
# gen_estimate -- doesnt' maek sense anymore
# active -- can we just derive this?
# late -- same as active
# contended -- cant happen anymore

def dot_task(task: InputTask, decoration: Decoration):
    wrap_desc      = '<br/>'.join(textwrap.wrap(html.escape(task.description), width=70))
    title          = title_format(style_text(task.name, bold = decoration.critical))

    start_date     = style_text(task.start_date)
    start_color    = 'white'

    end_date       = style_text(f'{task.end_date}')
    end_color      = 'white'

    estimate       = style_text(f"{task.estimate}d")
    estimate_color = 'white'

    border_width = 2
    border_color = 'black'
    today = datetime.now().date()
    if task.end_date and today > task.end_date:
        border_width = 4
        border_color = 'red'
    # As long as it's in progress it's OK
    elif task.start_date and today >= task.start_date:
        if task.status != Status.InProgress:
            border_width = 4
            border_color = 'red'
        else:
            border_width = 4
            border_color = 'lightgreen'
    elif task.start_date and busdays_between(today, task.start_date) <= SOON_THRESHOLD:
        border_width = 4
        border_color = 'lightyellow'

    assignees = ''
    if len(task.assignees) > 0:
        assignees = ', '.join(task.assignees)
    assignee_color = 'white'
    # Milestones are tasks with zero days estimated effort.
    if task.estimate == 0:
        return (
            f"{task.scheduler_fields.id} [label=<"
            f"<table border='1' cellborder='1' cellspacing='0'><tr><td>{title}</td></tr>"
            f"<tr><td bgcolor='{end_color}'>{end_date}</td></tr>"
            f"<tr><td bgcolor='#FFD580'> {wrap_desc}</td></tr></table>"
            f">];"
        )

    # A regular task.
    match task.status:
        case Status.Completed:
            return (
                f"{task.scheduler_fields.id} [label=<"
                f"<table border='1' color='lightblue' cellborder='1' cellspacing='0'><tr><td color='black' bgcolor='lightblue'>{title} (done)</td></tr>"
                f"<tr><td color='black' bgcolor='{end_color}'>{end_date}</td></tr></table>"
                f">];"
            )
        case Status.NotStarted:
            return (
                f"{task.scheduler_fields.id} [label=<"
                f"<table border='{border_width}' color='{border_color}' cellborder='1' cellspacing='0'><tr><td color='black' colspan='2'>{title}</td></tr>"
                f"<tr><td color='black' bgcolor='{start_color}'>{start_date}</td><td color='black' bgcolor='{end_color}'>{end_date}</td></tr>"
                f"<tr><td color='black' bgcolor='{assignee_color}'>{assignees}</td><td color='black' bgcolor='{estimate_color}'>{estimate}</td></tr>"
                f"<tr><td color='black' colspan='2'>{wrap_desc}</td></tr></table>"
                f">];"
            )
        case _:
            status_color = 'red' if task.status == 'blocked' else 'lightgreen' if task.status == 'in progress' else 'white'
            return (
                f"{task.scheduler_fields.id} [label=<"
                f"<table border='{border_width}' color='{border_color}' cellborder='1' cellspacing='0'><tr><td color='black' colspan='3' bgcolor='{status_color}'>{title}</td></tr>"
                f"<tr><td color='black' bgcolor='{start_color}'>{start_date}</td><td color='black' bgcolor='{status_color}'>{task.status}</td><td color='black' bgcolor='{end_color}'>{end_date}</td></tr>"
                f"<tr><td color='black' bgcolor='{assignee_color}' colspan='2'>{assignees}</td><td color='black' bgcolor='{estimate_color}'>{estimate}</td></tr>"
                f"<tr><td color='black' colspan='3'>{wrap_desc}</td></tr></table>"
                f">];"
            )

def generate_dot_file(G, decorations: Dict[InputTask, Decoration]):
    # Graph top-level.
    dot_file = (
        'digraph Items {\n'
        'rankdir=LR;\n'
        'node [fontname="Calibri,sans-serif" fontsize="12pt" shape=plaintext];\n'
        'edge [fontname="Calibri,sans-serif" fontsize="10pt"];\n'
    )

    # Write out all task nodes.
    dot_file += '\n'.join([dot_task(task, decorations[task]) for task in G.nodes])

    # Add in the edges.
    for u, v, edge in G.edges(data=True):
        color = 'gray'
        width = 1
        label = ''
        if edge[Edge.critical]:
            color = 'black'
            width = 4        
        if edge[Edge.slack] > 0:
            label = f"+{edge[Edge.slack]}d"
        elif edge[Edge.slack] < 0:
            color = 'red'
            label = f"late {abs(edge[Edge.slack])}d"            
        dot_file += f"{u.scheduler_fields.id} -> {v.scheduler_fields.id} [color={color}, penwidth={width}, label=\"{label}\"];\n"

    dot_file += '}\n'
    return dot_file

# Generate dot content and return b64 encoded representation
def generate_svg_graph(G, decorations):
    dot_content = generate_dot_file(G, decorations)
    
    # Save dot_content to a temporary file
    with tempfile.NamedTemporaryFile(delete=False, mode='w', suffix='.dot') as dotfile:
        dotfile_path = dotfile.name
        dotfile.write(dot_content)

    # Define the output PNG file path
    output_svg_path = dotfile_path + '.svg'

    # Call Graphviz dot to render PNG
    print(output_svg_path)
    dot_path = os.getenv('DOT_PATH', 'dot')
    subprocess.run([dot_path, '-Tsvg', dotfile_path, '-o', output_svg_path], check=True)
    with open(output_svg_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
