import datetime
import numpy as np

def busdays_between(start, end):
    return np.busday_count(start, end)

def compare_busdays(start, end, estimate):
    return estimate - busdays_between(start, end)

def busdays_offset(date, days):
    return np.busday_offset(date, days, roll='forward').astype(datetime.datetime)
