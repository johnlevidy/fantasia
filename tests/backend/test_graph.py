import pytest
from backend.graph import compute_dag_metrics, find_cycle 

def test_cycle():
    tasks = [
        {'Task': 'Order Corn Seed', 'Estimate': '5', 'next': ['Grow Corn', 'Plan Maze']},
        {'Task': 'Grow Corn', 'Estimate': '20', 'next': ['Cut Corn to Shape']},
        {'Task': 'Plan Maze', 'Estimate': '3', 'next': ['Cut Corn to Shape', 'Order Corn Seed']},
        {'Task': 'Cut Corn to Shape', 'Estimate': '3', 'next': ['Done']},
        {'Task': 'Done', 'Estimate': '0', 'next': []}
    ]
    cycle = find_cycle(tasks)
    assert cycle
    assert cycle[0] == 'Order Corn Seed'
    assert cycle[1] == 'Plan Maze'
    assert cycle[2] == 'Order Corn Seed'

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
    total_work, longest_path = compute_dag_metrics(tasks)
    assert not find_cycle(tasks)
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

    total_work, longest_path = compute_dag_metrics(tasks)
    assert total_work == 50
    assert longest_path ==  30
