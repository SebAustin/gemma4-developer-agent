from g4agent.eval_locate import gold_files, ranked_files

PATCH = """\
--- a/fastapi/routing.py
+++ b/fastapi/routing.py
@@ -1 +1 @@
-a
+b
--- a/tests/test_routing.py
+++ b/tests/test_routing.py
@@ -1 +1 @@
-a
+b
--- /dev/null
+++ b/docs_src/app/tutorial001.py
@@ -0,0 +1 @@
+x
--- a/docs/en/index.md
+++ b/docs/en/index.md
"""


def test_gold_files_keeps_source_and_docs_examples_but_not_tests_or_markdown():
    assert gold_files(PATCH) == ["fastapi/routing.py", "docs_src/app/tutorial001.py"]


def test_ranked_files_parses_locate_output():
    out = "query terms: a, b\n\n   12.3  fastapi/routing.py  [def x@3]\n    4.0  fastapi/utils.py\n"
    assert ranked_files(out) == ["fastapi/routing.py", "fastapi/utils.py"]
