import pytest
from networkx import NetworkXNoCycle
from backend.graph import compute_dag_metrics, find_cycle, find_bad_start_end_dates, find_overlapping_start_end_dates, build_graph, find_unstarted_items

def test_cycle():
    tasks = [
        {'Task': 'Order Corn Seed', 'Estimate': '5', 'next': ['Grow Corn', 'Plan Maze']},
        {'Task': 'Grow Corn', 'Estimate': '20', 'next': ['Cut Corn to Shape']},
        {'Task': 'Plan Maze', 'Estimate': '3', 'next': ['Cut Corn to Shape', 'Order Corn Seed']},
        {'Task': 'Cut Corn to Shape', 'Estimate': '3', 'next': ['Done']},
        {'Task': 'Done', 'Estimate': '0', 'next': []}
    ]
    cycle = find_cycle(build_graph(tasks))
    print(cycle)
    assert cycle
    assert cycle[0][0] == 'Order Corn Seed'
    assert cycle[0][1] == 'Plan Maze'
    assert cycle[1][1] == 'Order Corn Seed'
    assert cycle[1][0] == 'Plan Maze'

def test_find_unstarted_items():
    tasks = [
        {'Task': 'UniqueNameA', 'Estimate': '3', 'StartDate': '2022-05-22', 'EndDate': '2022-05-25', 'next': ['UniqueNameB']},
        {'Task': 'UniqueNameB', 'Estimate': '20', 'StartDate': '2022-05-22', 'EndDate': '2022-05-25', 'next': []},
    ]
    notifications = []
    find_unstarted_items(build_graph(tasks), notifications)
    assert len(notifications) == 1
    assert "[UniqueNameA] has an end date after next task" in notifications[0].message
    tasks = [
        {'Task': 'UniqueNameA', 'Estimate': '3', 'StartDate': '2022-05-22', 'EndDate': '2022-05-25', 'next': ['UniqueNameB']},
        {'Task': 'UniqueNameB', 'Estimate': '20', 'StartDate': '2022-05-25', 'EndDate': '2022-05-25', 'next': []},
    ]
    find_unstarted_items(build_graph(tasks), notifications)
    notifications = []
    assert not notifications

def test_find_overlapping_start_end_dates():
    tasks = [
        {'Task': 'UniqueNameA', 'Estimate': '3', 'StartDate': '2022-05-22', 'EndDate': '2022-05-25', 'next': ['UniqueNameB']},
        {'Task': 'UniqueNameB', 'Estimate': '20', 'StartDate': '2022-05-22', 'EndDate': '2022-05-25', 'next': []},
    ]
    notifications = []
    assert find_overlapping_start_end_dates(build_graph(tasks), notifications)
    assert '[UniqueNameB] has start date' in notifications[0].message
    tasks = [
        {'Task': 'UniqueNameA', 'Estimate': '3', 'StartDate': '2022-05-22', 'EndDate': '2022-05-25', 'next': ['UniqueNameB']},
        {'Task': 'UniqueNameB', 'Estimate': '20', 'StartDate': '2022-05-25', 'EndDate': '2022-06-25', 'next': []},
    ]
    assert not find_overlapping_start_end_dates(build_graph(tasks), notifications)

def test_find_bad_start_end_dates():
    tasks = [
        {'Task': 'A', 'Estimate': '3', 'StartDate': '2022-05-22', 'EndDate': '2022-05-25', 'next': []},
    ]
    notifications = []
    assert not find_bad_start_end_dates(build_graph(tasks), notifications)
    tasks = [
        {'Task': 'UniqueNameA', 'Estimate': '3', 'StartDate': '2022-05-22', 'EndDate': '2022-05-25', 'next': []},
        {'Task': 'UniqueNameB', 'Estimate': '20', 'StartDate': '2022-05-22', 'EndDate': '2022-05-25', 'next': []},
    ]
    assert find_bad_start_end_dates(build_graph(tasks), notifications)
    assert 'UniqueNameB' in notifications[0].message

def test_compute_dag_metrics():
    # Define a sample set of tasks similar to what you might have in your application
    tasks = [
        {'Task': 'Order Corn Seed', 'Estimate': '5', 'next': ['Grow Corn', 'Plan Maze']},
        {'Task': 'Grow Corn', 'Estimate': '20', 'next': ['Cut Corn to Shape']},
        {'Task': 'Plan Maze', 'Estimate': '3', 'next': ['Cut Corn to Shape']},
        {'Task': 'Cut Corn to Shape', 'Estimate': '3', 'next': ['Done']},
        {'Task': 'Done', 'Estimate': '0', 'next': []}
    ]

    # Execute the function under test
    total_work, longest_path = compute_dag_metrics(build_graph(tasks))
    try:
        find_cycle(build_graph(tasks))
        assert False
    except NetworkXNoCycle:
        assert True

    assert total_work == 31
    assert longest_path == 28

    tasks = [
        {'Task': 'Initialize Project', 'Estimate': '2', 'next': ['Setup Backend', 'Setup Frontend', 'Setup Database']},
        {'Task': 'Setup Backend', 'Estimate': '10', 'next': ['Integrate Database', 'User Authentication Module']},
        {'Task': 'Setup Frontend', 'Estimate': '8', 'next': ['User Interface Design', 'Frontend-Backend Integration']},
        {'Task': 'Setup Database', 'Estimate': '5', 'next': ['Integrate Database']},
        {'Task': 'User Authentication Module', 'Estimate': '5', 'next': ['Frontend-Backend Integration']},
        {'Task': 'User Interface Design', 'Estimate': '7', 'next': ['Frontend-Backend Integration']},
        {'Task': 'Integrate Database', 'Estimate': '3', 'next': ['User Authentication Module', 'Frontend-Backend Integration']},
        {'Task': 'Frontend-Backend Integration', 'Estimate': '4', 'next': ['Final Testing']},
        {'Task': 'Final Testing', 'Estimate': '4', 'next': ['Deployment']},
        {'Task': 'Deployment', 'Estimate': '2', 'next': ['Project Completed']},
        {'Task': 'Project Completed', 'Estimate': '0', 'next': []}
    ]

    total_work, longest_path = compute_dag_metrics(build_graph(tasks))
    assert total_work == 50
    assert longest_path ==  30
