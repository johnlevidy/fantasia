from backend.csv_parser import try_csv

fruit_plan = """Fruit,Task
Banana,Eat
Apple,Throw"""

def test_success():
    error_string = []
    try_csv(fruit_plan, error_string, delimiter = ",")
    print(error_string)

def test_empty():
    error_string = []
    try_csv("", error_string, delimiter = ",")
    print(error_string)
