"""The bundled task suite.

Design constraints (see docs/PREREGISTRATION.md):

* 30 tasks, split dev/test, five categories, six each.
* Every task is deterministic and runs offline with the scripted model.
* Categories are chosen so that *execution strategy* can matter:
    coding       - short, well-scoped; a plain loop is enough
    terminal     - tool-heavy; shell + filesystem round trips
    recovery     - the first approach breaks; escalation is the point
    migration    - a rewrite against a changed interface
    long_horizon - five or more dependent steps

* `oracle_prefer` records which harness actually wins on that task, measured by
  running the fixed arms. It is only used by the offline oracle arm.

The scripts are what the *scripted* model does under each harness. They are the
control for the experiment, not a claim about a real model's behaviour; the
pre-registration says the headline numbers require a live model.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class BenchTask:
    id: str
    category: str
    split: str
    instruction: str
    seed: dict[str, str] = field(default_factory=dict)
    grader: dict[str, Any] = field(default_factory=dict)
    budget: dict[str, float] = field(default_factory=lambda: {"max_actions": 16, "max_usd": 0.60})
    script_native: list[dict[str, Any]] = field(default_factory=list)
    script_langgraph: list[dict[str, Any]] = field(default_factory=list)
    script_repair: list[dict[str, Any]] = field(default_factory=list)
    oracle_prefer: str = "native"

    def grader_spec(self) -> str:
        return json.dumps(self.grader, sort_keys=True)


def _coding(n: int, split: str) -> BenchTask:
    module = f"mod_{n}"
    content = f"def value(x):\n    return x * {n}\n"
    check = f"from {module} import value\nassert value(3) == {3 * n}, value(3)\nprint('PASS')\n"
    script = [
        {"thought": f"write {module}.py implementing value()", "tool": "write_file",
         "args": {"path": f"{module}.py", "content": content}},
        {"thought": "module written and the checker imports it", "final": "done"},
    ]
    return BenchTask(
        id=f"coding-{n:02d}", category="coding", split=split,
        instruction=f"Create {module}.py in the workspace defining value(x) that returns x*{n}.",
        seed={"check.py": check},
        grader={"kind": "stdout_contains", "path": "check.py", "text": "PASS"},
        script_native=list(script), script_langgraph=list(script), script_repair=list(script),
        oracle_prefer="native",
    )


def _terminal(n: int, split: str) -> BenchTask:
    words = [f"w{n}{k}" for k in range(n + 2)]
    seed = {"input.txt": "\n".join(words) + "\n"}
    gen = (
        "from pathlib import Path\n"
        "words = Path('input.txt').read_text().split()\n"
        "Path('out.txt').write_text('\\n'.join(sorted(set(words))) + '\\n')\n"
        "print('generated')\n"
    )
    script = [
        {"thought": "inspect the workspace", "tool": "list_dir", "args": {"path": "."}},
        {"thought": "write the generator", "tool": "write_file", "args": {"path": "gen.py", "content": gen}},
        {"thought": "run it through the shell", "tool": "run_command", "args": {"command": "python gen.py"}},
        {"thought": "deduplicated and sorted", "final": "done"},
    ]
    return BenchTask(
        id=f"terminal-{n:02d}", category="terminal", split=split,
        instruction="Produce out.txt containing the unique words from input.txt, one per line, sorted.",
        seed=seed, grader={"kind": "file_contains", "path": "out.txt", "text": f"w{n}1"},
        script_native=list(script), script_langgraph=list(script), script_repair=list(script),
        oracle_prefer="native",
    )


def _recovery(n: int, split: str) -> BenchTask:
    broken = "def compute():\n    raise RuntimeError('missing dependency wiring')\n\nprint(compute())\n"
    fixed = f"def compute():\n    return 'OK-{n}'\n\nprint(compute())\n"
    native = [
        {"thought": "just run the module and see what happens", "tool": "run_command",
         "args": {"command": "python broken.py"}},
    ]
    langgraph = [
        {"thought": "read the failing module first", "tool": "read_file", "args": {"path": "broken.py"}},
        {"thought": "rewrite it with the missing wiring implemented", "tool": "write_file",
         "args": {"path": "broken.py", "content": fixed}},
        {"thought": "re-run the module", "tool": "run_command", "args": {"command": "python broken.py"}},
        {"thought": "the module now prints the expected value", "final": "done"},
    ]
    # The repair harness already loaded broken.py in on_start, so the scripted
    # policy edits and reruns. It does not spend a model call on the read, and
    # it does not crash the process before the edit.
    repair = [
        {"thought": "rewrite the module the diagnosis already loaded", "tool": "write_file",
         "args": {"path": "broken.py", "content": fixed}},
        {"thought": "run the repaired module", "tool": "run_command", "args": {"command": "python broken.py"}},
        {"thought": "the module now prints the expected value", "final": "done"},
    ]
    return BenchTask(
        id=f"recovery-{n:02d}", category="recovery", split=split,
        instruction="broken.py fails at runtime. Make it print its expected value.",
        seed={"broken.py": broken},
        grader={"kind": "stdout_contains", "path": "broken.py", "text": f"OK-{n}"},
        script_native=native, script_langgraph=langgraph, script_repair=repair,
        oracle_prefer="repair",
    )


def _migration(n: int, split: str) -> BenchTask:
    old = (
        "import json\n\n"
        "def load(payload):\n"
        "    return json.loads(payload)\n\n"
        "if __name__ == '__main__':\n"
        "    print(load('{\"v\": %d}')['v'])\n" % n
    )
    new = (
        "import json\n\n"
        "def load(payload: str) -> dict:\n"
        "    '''Parse a JSON document.'''\n"
        "    return json.loads(payload)\n\n"
        "if __name__ == '__main__':\n"
        "    print(load('{\"v\": %d}')['v'])\n" % n
    )
    script = [
        {"thought": "read the module to see the current interface", "tool": "read_file", "args": {"path": "legacy.py"}},
        {"thought": "rewrite it against the documented interface", "tool": "write_file",
         "args": {"path": "legacy.py", "content": new}},
        {"thought": "run it to confirm the value", "tool": "run_command", "args": {"command": "python legacy.py"}},
        {"thought": "migrated", "final": "done"},
    ]
    return BenchTask(
        id=f"migration-{n:02d}", category="migration", split=split,
        instruction="legacy.py uses the undocumented interface. Migrate it to the typed, documented one.",
        seed={"legacy.py": old},
        grader={"kind": "all_of", "specs": [
            {"kind": "file_contains", "path": "legacy.py", "text": "-> dict"},
            {"kind": "stdout_contains", "path": "legacy.py", "text": str(n)},
        ]},
        script_native=list(script), script_langgraph=list(script), script_repair=list(script),
        oracle_prefer="native",
    )


def _long_horizon(n: int, split: str) -> BenchTask:
    seed = {"config.json": json.dumps({"name": f"svc-{n}", "replicas": n})}
    report = (
        "import json\n"
        "from pathlib import Path\n"
        "cfg = json.loads(Path('config.json').read_text())\n"
        "Path('summary.txt').write_text(f\"{cfg['name']}:{cfg['replicas'] * 2}\")\n"
        "print('summary written')\n"
    )
    script = [
        {"thought": "list the workspace", "tool": "list_dir", "args": {"path": "."}},
        {"thought": "read the config", "tool": "read_file", "args": {"path": "config.json"}},
        {"thought": "write a report generator", "tool": "write_file", "args": {"path": "report.py", "content": report}},
        {"thought": "run the generator", "tool": "run_command", "args": {"command": "python report.py"}},
        {"thought": "verify the artifact", "tool": "read_file", "args": {"path": "summary.txt"}},
        {"thought": "complete", "final": "done"},
    ]
    return BenchTask(
        id=f"long-horizon-{n:02d}", category="long_horizon", split=split,
        instruction="Read config.json and produce summary.txt of the form name:replicas*2.",
        seed=seed, grader={"kind": "file_contains", "path": "summary.txt", "text": f"svc-{n}:{2 * n}"},
        script_native=list(script), script_langgraph=list(script), script_repair=list(script),
        oracle_prefer="native",
    )


BUILDERS = {
    "coding": _coding,
    "terminal": _terminal,
    "recovery": _recovery,
    "migration": _migration,
    "long_horizon": _long_horizon,
}


def all_tasks() -> list[BenchTask]:
    tasks: list[BenchTask] = []
    for category, build in BUILDERS.items():
        for i in range(1, 7):
            # 3 dev / 3 test per category, split before any results are seen.
            split = "dev" if i <= 3 else "test"
            tasks.append(build(i, split))
    return tasks


def by_split(split: str) -> list[BenchTask]:
    return [t for t in all_tasks() if t.split == split]