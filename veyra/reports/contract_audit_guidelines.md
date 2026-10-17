# Contract Inference Audit Guidelines (Frozen Protocol)

## Purpose
Evaluate how often naive verb-and-naming heuristics correctly infer execution safety contracts (side-effect classification) against ground-truth domain semantics for real tools, and measure the rate of **unsafe-direction errors** (classifying a mutating or non-idempotent operation as read-only or idempotent).

## Classification Schema

Each tool operation must be assigned to exactly one of three classes:

1. **`READ_ONLY`**:
   - The operation performs read, search, listing, inspection, query, parsing, or mathematical computation.
   - It induces zero persistent state changes in the underlying system or external services.
   - Safe to execute repeatedly and unconditionally.

2. **`IDEMPOTENT_WRITE`**:
   - The operation mutates state, but calling it multiple times with the exact same arguments produces the exact same final state.
   - Examples:
     - Overwriting a specific file path with full contents (`write_file`).
     - Setting a configuration key or status flag to a specific value.
     - Deleting a named entity or resource by ID/path (`delete_file`, `delete_entities`).
   - Safe to replay upon an uncertain timeout, provided parameters are unchanged.

3. **`NON_IDEMPOTENT_MUTATION`**:
   - The operation mutates state such that replaying it produces duplicate effects or alters state cumulatively.
   - Examples:
     - Appending content to an existing file (`append_file`).
     - Inserting records with auto-generated IDs into a database table.
     - Sending outbound messages, emails, notifications, or financial transfers.
     - Incrementing counters, moving files across paths, or triggering external webhooks.
   - Unsafe to replay blindly upon timeout.

## Error Direction Definitions

- **Safe-Direction Error**:
  - The inferred classification is *more restrictive* than the ground truth (e.g. ground truth is `IDEMPOTENT_WRITE`, but inferred is `NON_IDEMPOTENT_MUTATION`).
  - *Impact*: Triggers unnecessary confirmation prompts or disables auto-replay, but does **not** compromise safety or cause duplicate effects.

- **Unsafe-Direction Error**:
  - The inferred classification is *less restrictive* than the ground truth (e.g. ground truth is `NON_IDEMPOTENT_MUTATION`, but inferred is `READ_ONLY` or `IDEMPOTENT_WRITE`).
  - *Impact*: Allows unintended state changes to execute without confirmation or causes duplicate mutations on blind replay. High severity.
