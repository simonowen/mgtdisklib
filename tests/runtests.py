#!/usr/bin/env python3

import os
import unittest

if __name__ == "__main__":
    tests = unittest.defaultTestLoader.discover(os.path.dirname(__file__))
    unittest.TextTestRunner().run(tests)
