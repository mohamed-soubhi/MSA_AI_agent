"""Make the assignment2 package importable from tests/ without installing it,
and surface each test's @pytest.mark.tid id in normal `-v` output.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "agent")))


def pytest_itemcollected(item):
    """Append "[TID-001]" to the displayed node id for tests with a tid marker.

    Markers alone don't print in -v output; this makes the id visible in
    the terminal without renaming any test function.
    """
    marker = item.get_closest_marker("tid")
    if marker:
        item._nodeid = f"{item._nodeid} [{marker.args[0]}]"
