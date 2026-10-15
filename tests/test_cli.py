import unittest

from tests import helpers  # noqa: F401
from ai_book2video import cli


class CliTests(unittest.TestCase):
    def test_scene_ranges(self):
        self.assertEqual(cli.parse_scenes("1,3,5-7"), {1, 3, 5, 6, 7})
        self.assertIsNone(cli.parse_scenes(None))


if __name__ == "__main__":
    unittest.main()
