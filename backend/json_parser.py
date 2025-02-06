from .notification import Notification, Severity
from .types import Metadata
import json

def try_json(data, notifications):
    try:
        parsed_json = json.loads(data)
        return parsed_json, Metadata() # no Metadata support in JSON right now.
    except json.JSONDecodeError as e:
        notifications.append(Notification(Severity.ERROR, f"Invalid JSON ( json.loads threw: \"{str(e)})\""))
    return None, None
