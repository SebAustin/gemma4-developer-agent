---
name: swe
description: Fast repository navigation, targeted test running and a pre-submit patch check for fixing issues in the Python repo at /workspace. Scripts print compact, ranked results.
---
# swe: repository tools

Call scripts directly with `run_skill_script` and `skill_name="swe"`. Pass arguments as a list of strings in `args`. Every script searches the repository at /workspace and never modifies it.

| Goal | file_path | args example |
|---|---|---|
| Rank files relevant to the issue | `scripts/locate.py` | `["APIRouter include_router prefix dependencies"]` |
| Definition and usages of a symbol | `scripts/symbol.py` | `["Console.print"]` |
| Structure of a file (classes/functions with line ranges) | `scripts/outline.py` | `["src/pkg/module.py"]` |
| Numbered source of one symbol | `scripts/outline.py` | `["src/pkg/module.py", "--symbol", "Class.method"]` |
| Regex search, grouped by file | `scripts/grep.py` | `["def get_\\w+", "--path", "src"]` or `["exact text", "--fixed"]` |
| Tests related to a source file or symbol | `scripts/tests.py` | `["find", "src/pkg/module.py"]` |
| Run specific tests, compact summary | `scripts/tests.py` | `["run", "tests/test_module.py", "-k", "keyword"]` |
| Pre-submit check of the diff | `scripts/check_patch.py` | `[]` |

Notes
- `locate.py` accepts free text: paste the key identifiers, error message and quoted strings from the issue.
- `tests.py run` refuses to run the whole suite; always give test files or node ids such as `tests/test_x.py::test_name`.
- `check_patch.py` reports BLOCKING problems (syntax errors, scratch files that would leak into the patch, empty diff). Fix them before calling `submit_patch`.
