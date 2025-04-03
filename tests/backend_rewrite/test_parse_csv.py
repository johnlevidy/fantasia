from backend_rewrite.parse_csv import csv_string_to_task_list
from backend_rewrite.types import  Status, InputTask

import datetime
import unittest

class TestParseCSV(unittest.TestCase):
    def test_basic_parse(self):
        input = '''Task|Estimate|StartDate|EndDate|Status|Assignee|next
        %TEAM|All|Michael|John
        TaskA|5|2025-04-02|2025-04-08|not started|Michael|TaskC
        TaskB|6|2025-04-02|2025-04-08|in progress|Michael|TaskC
        %TEAM|Other|Michael|John
        TaskC|7|2025-04-02|2025-04-08|completed|Michael|TaskD
        TaskD|0|2025-04-08|2025-04-11|milestone|John|'''

        res = csv_string_to_task_list(input, '|')
        start_date = datetime.date(2025, 4, 2)
        medium_date = datetime.date(2025, 4, 8)
        end_date = datetime.date(2025, 4, 11)

        self.assertEqual(res[0], InputTask("TaskA", "desc", ['Michael'], ['TaskC'], 5, start_date, medium_date, Status.NotStarted, 1))
        self.assertEqual(res[1], InputTask("TaskB", "desc", ['Michael'], ['TaskC'], 6, start_date, medium_date, Status.InProgress, 2))
        self.assertEqual(res[2], InputTask("TaskC", "desc", ['Michael'], ['TaskD'], 7, start_date, medium_date, Status.Completed, 4))
        self.assertEqual(res[3], InputTask("TaskD", "desc", ['John'], [], 0, medium_date, end_date, Status.Milestone, 5))

    def test_no_headers(self):
        input = '''Task|Estimate|StartDate|EndDate|Status|Assignee|next'''
        fields = input.split('|')
        # Generate permutations by omitting each field one at a time
        permutations = ['|'.join(fields[:i] + fields[i+1:]) for i in range(len(fields))]
        for p in permutations:
            with self.assertRaisesRegex(Exception, f"No header.*"):
                csv_string_to_task_list(p, '|')

    def test_bad_estimate(self):
        input = '''Task|Estimate|StartDate|EndDate|Status|Assignee|next
        TaskA|5_is_bad|2025-04-02|2025-04-08|not started|Michael|TaskC'''
        with self.assertRaisesRegex(Exception, "Got estimate: 5_is_bad"):
            csv_string_to_task_list(input, '|')

    def test_bad_date(self):
        input = '''Task|Estimate|StartDate|EndDate|Status|Assignee|next
        TaskA|5|20250402|2025-04-08|not started|Michael|TaskC'''
        with self.assertRaisesRegex(Exception, "time data.*does not match"):
            csv_string_to_task_list(input, '|')

    def test_no_data(self):
        input = ''''''
        with self.assertRaisesRegex(Exception, "No data in csv string"):
            csv_string_to_task_list(input, '|')

    def test_bad_status(self):
        input = '''Task|Estimate|StartDate|EndDate|Status|Assignee|next
        TaskA|5|2025-04-02|2025-04-08|banana|Michael|TaskC'''
        with self.assertRaisesRegex(Exception, "banana"):
            csv_string_to_task_list(input, '|')
