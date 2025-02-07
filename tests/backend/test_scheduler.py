import pytest

from backend.scheduler import get_people
from backend.types import Metadata

def test_get_assignees():
    m = Metadata()
    m.add_person('T1', 'P1')
    m.add_person('T1', 'P2')
    m.add_person('T1', 'P3')
    m.add_person('T2', 'P4')
    assert get_people([], m)                    == [(1, ['Anon'])]
    assert get_people(['P1'], m)                == [(1, ['P1'])]
    assert get_people(['T1'], m)                == [(1, ['P1', 'P2', 'P3'])]
    assert get_people(['T1(2)'], m)             == [(2, ['P1', 'P2', 'P3'])]
    assert get_people(['T1(5)'], m)             == [(3, ['P1', 'P2', 'P3'])]
    assert get_people(['P2', 'T1(2)'], m)       == [(1, ['P1', 'P3']), (1, ['P2'])]
    assert get_people(['P2', 'P3', 'T1(2)'], m) == [(1, ['P2']), (1, ['P3'])]
    assert get_people(['P2', 'P3', 'T1(3)'], m) == [(1, ['P1']), (1, ['P2']), (1, ['P3'])]

