"""Make BE/app importable from BE/tests without installing it as a
package -- same pattern as tests/conftest.py at the project root."""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
