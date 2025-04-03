import networkx as nx
from networkx import DiGraph
from .types import InputTask
from .dateutil import busdays_between
from datetime import datetime
from .notification import Notification, Severity
from typing import Tuple

def compute_total_work_longest_path(G: DiGraph) -> Tuple[int, int]:
    total_work = sum(task.estimate for task in G.nodes)
    longest_path = nx.dag_longest_path_length(G)
    return total_work, longest_path

# Statefully updates notifications to include relevant graph related metrics
def output_graph_metrics(G: nx.DiGraph, notifications: list[Notification]) -> None:
    total_length, critical_path_length = compute_total_work_longest_path(G)
    parallelism_ratio = total_length / critical_path_length
    notifications.append(Notification(Severity.INFO, f"[Total Length: {total_length}], [Critical Path Length: {critical_path_length}], [Parallelism Ratio: {parallelism_ratio:.2f}]"))

SOON_THRESHOLD = 3
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

# Things I agree should be annotated on this graph

# Statefully enriches the graph with some more useful information
# def enrich_graph(G: nx.DiGraph[InputTask]) -> None:
#     # Today's date - tasks that contain this date are "active".
#     # TODO should match the user's timezone.
#     today = datetime.now().date()
# 
#     for task in G.nodes:
#         task.latest_start = busdays_between(task.start_date, task.end_date)
# 
#         task.busdays = busdays_between(task.start_date, task.end_date)
#         task.floot   = busdays_between(task.end_date, task.jit_end)
#         task.buffer  = task.busdays - task.estimate
#         if task.start_date > today:
#             task.soon = busdays_between(today, task.start_date) <= SOON_THRESHOLD 
#         else:
#             if today <= task.end_date:
#                 task.active = True
#             else:
#                 task.late = True
# 
#         # Calculate slack between this task and all successor tasks.
#         # Tasks following in progress or blocked tasks that are not started are "up next".
#         live = task.status == 'in progress' or task.status == 'blocked'
#         for succ in G.successors(task):
#             G.edges[task, succ][Edge.slack] = busdays_between(task.end_date, succ.start_date)
#             if live and succ.status == 'not started':
#                 succ.up_next = True
# 
#     # Tag the critical path.
#     critical_path = nx.dag_longest_path(G)
#     for task in critical_path:
#         task.critical = True
#     for edge in zip(critical_path, critical_path[1:]):
#         G.edges[edge][Edge.critical] = True
# 
