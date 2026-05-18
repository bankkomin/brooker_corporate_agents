"""Pytest configuration for services/shared unit tests.

Adds the services/shared directory to sys.path so that modules such as
`skills_loader` can be imported with their bare module name when running
pytest from within services/shared/.
"""
import sys
import os

# Ensure the services/shared directory is on sys.path for bare-name imports
# (e.g. `from skills_loader import SkillsLoader`).
_shared_dir = os.path.dirname(__file__)
if _shared_dir not in sys.path:
    sys.path.insert(0, _shared_dir)
