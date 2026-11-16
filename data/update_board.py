with open('docs/TASK_BOARD.md', 'r', encoding='utf-8') as f:
    text = f.read()

replacements = [
    (
        "| H1 | Move Phase A generators and result files out of `scratch/` (git-ignored) into a tracked folder; add ledger rows | Run | Files tracked, ledger has A1, A2, A3 and the recalibration control | todo |",
        "| H1 | Move Phase A generators and result files out of `scratch/` (git-ignored) into a tracked folder; add ledger rows | Run | Files tracked, ledger has A1, A2, A3 and the recalibration control | done |"
    ),
    (
        "| H2 | One conformal implementation everywhere (`soro/routing/conformal.py`); ties broken by a hash of the option key | Run | `eval_conformal_action.py` no longer clips | todo |",
        "| H2 | One conformal implementation everywhere (`soro/routing/conformal.py`); ties broken by a hash of the option key | Run | `eval_conformal_action.py` no longer clips | done |"
    ),
    (
        "| H3 | Reconcile 321 request groups against the \"115 base queries\" on the public 4B card | Run | One number, explained in the ledger | todo |",
        "| H3 | Reconcile 321 request groups against the \"115 base queries\" on the public 4B card | Run | One number, explained in the ledger | done |"
    ),
    (
        "| H4 | Reconcile 4B flips: 23/5,007 against 2/1,200 | Run | One row in the ledger with dtype and score spread | todo |",
        "| H4 | Reconcile 4B flips: 23/5,007 against 2/1,200 | Run | One row in the ledger with dtype and score spread | done |"
    ),
    (
        "| E1 | Attack suite v2. Lookalikes in the same JSON card format as real tools, no `fake_` in names. Two versions: request-aware, and request-blind (clone catalog tools with promotional metadata) | Run | Two files, generator tracked | todo |",
        "| E1 | Attack suite v2. Lookalikes in the same JSON card format as real tools, no `fake_` in names. Two versions: request-aware, and request-blind (clone catalog tools with promotional metadata) | Run | Two files, generator tracked | done |"
    ),
    (
        "| L1 | DecisionRobust (2610.19118), full text: any attack that adds or edits options? any tool tasks? any abstention or selective metrics? | Audit | todo |",
        "| L1 | DecisionRobust (2610.19118), full text: any attack that adds or edits options? any tool tasks? any abstention or selective metrics? | Audit | done |"
    ),
    (
        "| L2 | Jeva (2610.18773), full text: is each option's score independent of the others? how is the \"some option fits\" estimate computed? are weights released? | Audit | todo |",
        "| L2 | Jeva (2610.18773), full text: is each option's score independent of the others? how is the \"some option fits\" estimate computed? are weights released? | Audit | done |"
    ),
    (
        "| L3 | Is resolving by tool origin published? ETDI, FIDES, CaMeL, MCP registry signing. Does any allow a third-party tool to win over a trusted one? | Audit | todo |",
        "| L3 | Is resolving by tool origin published? ETDI, FIDES, CaMeL, MCP registry signing. Does any allow a third-party tool to win over a trusted one? | Audit | done |"
    )
]

for old, new in replacements:
    assert old in text, f"Target string not found:\n{old}"
    text = text.replace(old, new)

with open('docs/TASK_BOARD.md', 'w', encoding='utf-8') as f:
    f.write(text)

print("Successfully updated TASK_BOARD.md!")
