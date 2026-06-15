import unittest

import bili_stats


class PackageTest(unittest.TestCase):
    def test_version_uses_semantic_version_format(self):
        self.assertRegex(bili_stats.__version__, r"^\d+\.\d+\.\d+$")


if __name__ == "__main__":
    unittest.main()
