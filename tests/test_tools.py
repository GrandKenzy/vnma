"""Test suite for vnma developer tools (bigfiles, cacheclean, search)."""

from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from vnma.cli import build_parser
from vnma.core.context import ProjectContext
from vnma.tools.bigfiles import count_useful_lines, run_bigfiles
from vnma.tools.cacheclean import clean_caches, run_cacheclean
from vnma.tools.search import run_search, search_pattern_in_files


class TestBigfilesTool(unittest.TestCase):
    """Test bigfiles useful lines counting and CLI execution."""

    def test_count_useful_lines_python(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            f = Path(tmp_dir) / "sample.py"
            f.write_text(
                '"""Module docstring line 1\nLine 2\n"""\n'
                "# Single line comment\n"
                "\n"
                "x = 1\n"
                "y = 2\n"
                "# Another comment\n"
                "\n"
                "def func():\n"
                "    pass\n",
                encoding="utf-8",
            )
            useful, comments, blanks = count_useful_lines(f)
            # Useful: x=1, y=2, def func():, pass -> 4 useful lines
            self.assertEqual(useful, 4)
            # Comments: 3 docstring lines + 2 hash comment lines -> 5 comment lines
            self.assertEqual(comments, 5)
            # Blanks: 2 empty lines
            self.assertEqual(blanks, 2)

    def test_bigfiles_cli_threshold_filtering(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            f_small = root / "small.py"
            f_small.write_text("a = 1\nb = 2\n", encoding="utf-8")

            f_large = root / "large.py"
            f_large.write_text("\n".join(f"x_{i} = {i}" for i in range(15)) + "\n", encoding="utf-8")

            buf = io.StringIO()
            with redirect_stdout(buf):
                code = run_bigfiles(root, ["-l", "10"])

            self.assertEqual(code, 0)
            output = buf.getvalue()
            self.assertIn("large.py", output)
            self.assertNotIn("small.py", output)


class TestCachecleanTool(unittest.TestCase):
    """Test cacheclean directory and compiled file removal."""

    def test_clean_caches_removes_pycache_and_pyc(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            cache_dir = root / "pkg" / "__pycache__"
            cache_dir.mkdir(parents=True)
            (cache_dir / "mod.cpython-312.pyc").write_bytes(b"PYC_BYTECODE_DATA")

            standalone_pyc = root / "extra.pyc"
            standalone_pyc.write_bytes(b"EXTRA_BYTECODE")

            d_count, f_count, freed = clean_caches(root)
            self.assertEqual(d_count, 1)
            self.assertEqual(f_count, 2)
            self.assertGreater(freed, 0)
            self.assertFalse(cache_dir.exists())
            self.assertFalse(standalone_pyc.exists())


class TestSearchTool(unittest.TestCase):
    """Test search pattern matching and outputs filtering."""

    def test_search_pattern_in_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            f1 = root / "doc.md"
            f1.write_text("# Hello World\nSome special MD content\n", encoding="utf-8")

            f2 = root / "app.py"
            f2.write_text("def do_something():\n    return 'TOOL'\n", encoding="utf-8")

            matches, count = search_pattern_in_files([f1, f2], r"MD|TOOL")
            self.assertEqual(count, 2)
            self.assertEqual(len(matches), 2)

    def test_search_cli_with_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            f1 = root / "file1.txt"
            f1.write_text("needle in file1\n", encoding="utf-8")

            f2 = root / "file2.txt"
            f2.write_text("needle in file2\n", encoding="utf-8")

            buf = io.StringIO()
            with redirect_stdout(buf):
                code = run_search(root, ["needle", "--outputs", str(f1)])

            self.assertEqual(code, 0)
            output = buf.getvalue()
            self.assertIn("file1.txt", output)
            self.assertNotIn("file2.txt", output)


class TestToolsCliDispatch(unittest.TestCase):
    """Test vnma tools CLI dispatcher."""

    def test_tools_help_when_no_subcommand(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            context = ProjectContext(start_path=root)
            parser = build_parser()
            args = parser.parse_args(["tools"])

            buf = io.StringIO()
            with redirect_stdout(buf):
                code = args.handler(args, context)

            self.assertEqual(code, 0)
            self.assertIn("VNMA Developer Tools", buf.getvalue())

    def test_tools_unknown_tool_returns_1(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            context = ProjectContext(start_path=root)
            parser = build_parser()
            args = parser.parse_args(["tools", "unknown_tool_xyz"])

            buf = io.StringIO()
            with redirect_stdout(buf):
                code = args.handler(args, context)

            self.assertEqual(code, 1)
            self.assertIn("Unknown tool", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
