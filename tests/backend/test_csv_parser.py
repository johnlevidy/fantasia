from backend.csv_parser import try_csv

fruit_plan = """Fruit,Task
Banana,Eat
Apple,Throw"""

corn_plan = """id,EndDate,StartDate,Task,Description,Estimate,Assignee,Status,next
1,2022-05-22,2022-05-22,Order Corn Seed,Online order,5,Me,ongoing,Grow Corn,Plan Maze
2,2022-05-22,2022-05-22,Grow Corn,Plant and grow the corn,20,Me,ongoing,Cut Corn to Shape
3,2022-05-22,2022-05-22,Plan Maze,Think hard about a fun design,3,Me,blocked,Cut Corn to Shape
4,2022-05-22,2022-05-22,Cut Corn to Shape,Slice and dice,3,Me,ongoing,Done
5,2022-05-22,2022-05-22,Done,Project completed,0,Me,completed,
%TEAM,ALL,John,Mike"""

extra_rows = """id,EndDate,StartDate,Task,Description,Estimate,Assignee,Status,next
1,2022-05-22,2022-05-22,Order Corn Seed,Online order,5,Me,ongoing,Grow Corn,Plan Maze
,,,,,,,
,,,,,,,
,,,,,,,
,,,,,,,"""

def test_success():
    error_string = []
    data, metadata = try_csv(corn_plan, error_string, delimiter = ",")
    assert(data)
    assert(metadata)
    assert(len(metadata.people) == 2)
    assert(len(metadata.teams['ALL']) == 2)
    assert(len(data) == 5)
    assert(len(data[0]['next']) == 2)

def test_drop_extra_rows():
    error_string = []
    data, metadata = try_csv(extra_rows, error_string, delimiter = ",")
    assert(len(data) == 1)
    assert(len(data[0]['next']) == 2)

def test_empty():
    error_string = []
    try_csv("", error_string, delimiter = ",")
    assert(error_string[0].message.startswith('CSV appears empty'))
