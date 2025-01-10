import pytest
from backend.json_parser import try_json

def test_success():
    corn_project = '''[
{"Task": "Order Corn Seed", "Estimate": "5", "next": ["Grow Corn", "Plan Maze"]},
{"Task": "Grow Corn", "Estimate": "20", "next": ["Cut Corn to Shape"]},
{"Task": "Plan Maze", "Estimate": "3", "next": ["Cut Corn to Shape"]},
{"Task": "Cut Corn to Shape", "Estimate": "3", "next": ["Done"]},
{"Task": "Done", "Estimate": "0", "next": []}
]'''
    
    error_string = []
    try_json(corn_project, error_string)
    assert(len(error_string) == 0) 

def test_failure():
    # Obviously bad json
    bad_json = '''[
{"Task "Order Corn Seed", "Estimate": "5", "next": ["Grow Corn", "Plan Maze"]},
]'''
    
    error_string = []
    try_json(bad_json, error_string)
    assert(len(error_string) == 1) 
    assert(error_string[0].startswith("Invalid JSON"))
