from .notification import Notification, Severity
import json

def try_json(data, notifications):
    try:
        parsed_json = json.loads(data)
        return parsed_json
    except json.JSONDecodeError as e:
        notifications.append(Notification(Severity.ERROR, f"Invalid JSON ( json.loads threw: \"{str(e)})\""))
    return None
