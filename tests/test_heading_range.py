import json
import os
from datetime import datetime
import pytest

from mam_analyzer.utils.units import heading_within_range

def test_heading_range_correct():
    # Normal headings
    assert heading_within_range(100,120, tolerance=10) is False
    assert heading_within_range(100,120, tolerance=20) is True
    assert heading_within_range(120,100, tolerance=10) is False
    assert heading_within_range(120,100, tolerance=20) is True
    assert heading_within_range(100,80, tolerance=10) is False
    assert heading_within_range(100,80, tolerance=20) is True
    assert heading_within_range(80,100, tolerance=10) is False
    assert heading_within_range(80,100, tolerance=20) is True

    #Strange headings
    assert heading_within_range(5,345, tolerance=10) is False
    assert heading_within_range(5,345, tolerance=20) is True
    assert heading_within_range(345,5, tolerance=10) is False
    assert heading_within_range(345,5, tolerance=20) is True
    assert heading_within_range(360, 0, tolerance=10) is True
    assert heading_within_range(0, 360, tolerance=20) is True
    assert heading_within_range(15,355, tolerance=10) is False
    assert heading_within_range(15,355, tolerance=20) is True
    assert heading_within_range(355,15, tolerance=10) is False
    assert heading_within_range(355,15, tolerance=20) is True