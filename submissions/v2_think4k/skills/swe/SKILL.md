---
name: swe
description: Repository navigation, targeted tests and pre-submit patch check for the Python repo at /workspace. Load for script options beyond the call table in your instructions.
---
# swe scripts: options

Every script reads /workspace, leaves it unchanged, and keeps its output compact. Call with run_skill_script, skill_name "swe", and args as a list of strings, e.g. `args: ["Console.print"]`.

## scripts/locate.py TEXT... [--tests] [--top N]
Ranks source files by relevance to free text: identifiers, dotted names, backticked code, error messages. A file scores highest when it *defines* a symbol named in the text. Issue-template boilerplate and URLs are ignored. Test files are excluded unless you pass `--tests`. Output: score, path, and `[def name@line]` hits.

## scripts/symbol.py NAME [--refs N]
NAME may be `func`, `Class`, `Class.method` or a dotted suffix. Prints the definitions (file:line, signature, line range, first docstring line), then reference lines grouped by file, with source and tests listed separately.

## scripts/outline.py FILE [--symbol NAME]
Without `--symbol`, prints the classes and functions with line ranges, so you can pick read_file ranges. With `--symbol Class.method`, prints that symbol's numbered source, up to 200 lines.

## scripts/grep.py PATTERN [--path DIR] [--all-files] [-i] [--fixed] [--no-tests]
Python regex, run over .py files by default (`--all-files` adds docs and config). Use `--fixed` for literal text containing regex characters. Results are grouped by file, with up to 8 lines each.

## scripts/tests.py find TARGET | run TEST... [-k EXPR] [--timeout S]
`find` ranks the test files that mention a source file, module or symbol. `run` takes test files or node ids (`tests/test_x.py::test_y`) and prints the pytest summary line, the failed tests and short tracebacks. It accepts specific targets only.

## scripts/check_patch.py [--full]
Shows the diff exactly as submit_patch will capture it. BLOCKING items must be fixed first: an empty patch, a syntax error, or a scratch file inside /workspace. WARNING items explain what the grader discards, such as edits to test and config files. Prints OK when the patch is ready.
