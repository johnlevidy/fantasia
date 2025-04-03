from backend_rewrite.metadata import extract_metadata
from backend_rewrite.types import Status, InputTask, Person, Team
import datetime
import unittest

michael = Person("Michael")
john = Person("John")

# We use a bar delimiter on these tests because I need something that 
# doesn't conflict with comma-delimited Assignee
class TestMetadata(unittest.TestCase):
    def test_basic_parse(self):
        input = '''Task|Estimate|StartDate|EndDate|Status|Assignee|next
        %TEAM|All|Michael|John
        TaskA|5|2025-04-02|2025-04-08|not started|Michael|TaskC
        TaskB|6|2025-04-02|2025-04-08|in progress|Michael|TaskC
        %TEAM|Other|Michael|John
        TaskC|7|2025-04-02|2025-04-08|in progress|Michael|TaskD
        %ALLOCATION|John|.5
        %ALLOCATION|Michael|.9

        TaskD|0|2025-04-02|2025-04-08|milestone|Michael|TaskC
        '''
        res = extract_metadata(input, '|')
        self.assertEqual(res.teams[0], Team("All", [michael, john]))
        self.assertEqual(res.teams[1], Team("Other", [michael, john]))

    def test_override_allocation(self):
        input = '''Task|Estimate|StartDate|EndDate|Status|Assignee|next
        %ALLOCATION|Michael|.5
        %TEAM|All|Michael|John'''
        res = extract_metadata(input, '|')
        self.assertEqual(res.people_allocations[michael], .5)
        
    def test_empty_team(self):
        input = '''%TEAM'''
        with self.assertRaisesRegex(Exception, "Team declaration for.*"):
            extract_metadata(input, '|')
        input = '''%TEAM|All'''
        with self.assertRaisesRegex(Exception, "Team declaration for.*All"):
            extract_metadata(input, '|')
