# -*- coding: utf-8 -*-
from __future__ import unicode_literals

__version__ = '0.0.1'

# Import the cashfree module directly
import os
import sys

# Add the current directory to the path
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Import cashfree module
import cashfree as _cashfree_module
# Make it available as cashfree.cashfree
sys.modules['cashfree.cashfree'] = _cashfree_module