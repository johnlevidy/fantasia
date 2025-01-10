import json

def try_json(data, error_string):
    try:
        parsed_json = json.loads(data)
        return parsed_json
    except json.JSONDecodeError as e:
        error_string += [f"Invalid JSON ( json.loads threw: \"{str(e)})\""]
    return None
