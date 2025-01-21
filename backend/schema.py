from .notification import Notification, Severity

expected_columns = ['Estimate', 'Task', 'next', 'StartDate', 'EndDate', 'Status']
enum_constraints = { 'Status': ['in progress', 'blocked', 'milestone', 'completed', 'not started'] }

def verify_schema(parsed_content, notifications):
    for task in parsed_content:
        for expected in expected_columns:
            if expected not in task:
                notifications.append(Notification(Severity.FATAL, f"{task} did not contain key {expected}"))
                return False
            if expected in enum_constraints:
                if task[expected] not in enum_constraints[expected]:
                    notifications.append(Notification(Severity.FATAL, f"Row {task} had invalid value in key {expected}. Valid values are: {str(enum_constraints[expected])}"))
    return True

