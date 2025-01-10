# TODO: use this instead of error_string so we can determine severity at generation site
from enum import Enum

class Severity(Enum):
    INFO = 1
    ERROR = 2
    SEVERE = 3

class Error:
    def __init__(self, severity: Severity, message: str):
        if not isinstance(severity, Severity):
            raise ValueError("severity must be an instance of Severity enum")
        self.severity = severity
        self.message = message

    def __str__(self):
        return f'{self.severity.name}: {self.message}'
