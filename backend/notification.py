# TODO: use this instead of error_string so we can determine severity at generation site
from enum import Enum
import json

class Severity(Enum):
    INFO = 1
    ERROR = 2
    SEVERE = 3

class Notification:
    def __init__(self, severity: Severity, message: str):
        if not isinstance(severity, Severity):
            raise ValueError("severity must be an instance of Severity enum")
        self.severity = severity
        self.message = message

    def __str__(self):
        return f'{self.severity.name}: {self.message}'

    def to_dict(self):
        return {
                'severity': self.severity.name,
                'message': self.message
                }
