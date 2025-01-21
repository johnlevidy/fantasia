from datetime import datetime
import numpy as np

def busdays_between(start_date, end_date):
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    return np.busday_count(start.date(), end.date())

def compare_busdays(start_date, end_date, estimate):
    return estimate - busdays_between(start_date, end_date)

