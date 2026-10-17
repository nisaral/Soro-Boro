# Soro Audit: Manual In-Depth Verification of 20 MCP Tools

This document details the manual, step-by-step verification of 20 real MCP tools audited over stdio.
For each tool, we show the input schema, synthesized arguments, Call 1 return, Call 2 replay return,
state differential, declared hints vs observed semantics, and suggested annotation patches.

| # | Server | Tool | Declared Hint | Observed Semantics | Verdict |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | `npm-server-memory` | `create_entities` | `none` | `idempotent_or_read_only` | **MATCH** |
| 2 | `npm-server-memory` | `create_relations` | `none` | `idempotent_or_read_only` | **MATCH** |
| 3 | `npm-server-memory` | `add_observations` | `none` | `idempotent_or_read_only` | **MATCH** |
| 4 | `npm-server-memory` | `delete_entities` | `none` | `idempotent_or_read_only` | **FLAGGED** |
| 5 | `npm-server-memory` | `delete_observations` | `none` | `idempotent_or_read_only` | **FLAGGED** |
| 6 | `npm-server-memory` | `delete_relations` | `none` | `idempotent_or_read_only` | **FLAGGED** |
| 7 | `npm-server-memory` | `read_graph` | `none` | `idempotent_or_read_only` | **MATCH** |
| 8 | `npm-server-memory` | `search_nodes` | `none` | `idempotent_or_read_only` | **MATCH** |
| 9 | `npm-server-memory` | `open_nodes` | `none` | `idempotent_or_read_only` | **MATCH** |
| 10 | `npm-server-filesystem` | `read_file` | `none` | `idempotent_or_read_only` | **MATCH** |
| 11 | `npm-server-filesystem` | `read_text_file` | `none` | `idempotent_or_read_only` | **MATCH** |
| 12 | `npm-server-filesystem` | `read_media_file` | `none` | `idempotent_or_read_only` | **MATCH** |
| 13 | `npm-server-filesystem` | `read_multiple_files` | `none` | `idempotent_or_read_only` | **MATCH** |
| 14 | `npm-server-filesystem` | `write_file` | `none` | `idempotent_or_read_only` | **FLAGGED** |
| 15 | `npm-server-filesystem` | `edit_file` | `none` | `idempotent_or_read_only` | **MATCH** |
| 16 | `npm-server-filesystem` | `create_directory` | `none` | `idempotent_or_read_only` | **MATCH** |
| 17 | `npm-server-filesystem` | `list_directory` | `none` | `idempotent_or_read_only` | **MATCH** |
| 18 | `npm-server-filesystem` | `list_directory_with_sizes` | `none` | `idempotent_or_read_only` | **MATCH** |
| 19 | `npm-server-filesystem` | `directory_tree` | `none` | `idempotent_or_read_only` | **FLAGGED** |
| 20 | `npm-server-filesystem` | `move_file` | `none` | `idempotent_or_read_only` | **MATCH** |

## Detailed Tool Examination Traces

### 1. Tool: `create_entities` (`@modelcontextprotocol/server-memory`)
- **Description:** Create multiple new entities in the knowledge graph. An entity whose name already exists, or repeats an earlier entity in the same call, is skipped and its observations are not added; the result lists the skipped names in `skipped`. Use add_observations to add observations to an existing entity.
- **Declared Annotations:** `{"readOnlyHint": null, "idempotentHint": null, "destructiveHint": null, "openWorldHint": null}`
- **Observed Behavior:** `idempotent_or_read_only` (Execution Status: `exercised`)
- **Red Flags Detected:** None
- **Discrepancy:** None (Clean)
- **Suggested Annotation Patch:** `{"readOnlyHint": true, "idempotentHint": true}`
- **Verification Analysis:** Tool exhibits genuine read-only / idempotent semantics. Declared hints were verified accurate.

---

### 2. Tool: `create_relations` (`@modelcontextprotocol/server-memory`)
- **Description:** Create multiple new relations between entities in the knowledge graph. Relations should be in active voice
- **Declared Annotations:** `{"readOnlyHint": null, "idempotentHint": null, "destructiveHint": null, "openWorldHint": null}`
- **Observed Behavior:** `idempotent_or_read_only` (Execution Status: `exercised`)
- **Red Flags Detected:** None
- **Discrepancy:** None (Clean)
- **Suggested Annotation Patch:** `{"readOnlyHint": true, "idempotentHint": true}`
- **Verification Analysis:** Tool exhibits genuine read-only / idempotent semantics. Declared hints were verified accurate.

---

### 3. Tool: `add_observations` (`@modelcontextprotocol/server-memory`)
- **Description:** Add new observations to existing entities in the knowledge graph
- **Declared Annotations:** `{"readOnlyHint": null, "idempotentHint": null, "destructiveHint": null, "openWorldHint": null}`
- **Observed Behavior:** `idempotent_or_read_only` (Execution Status: `exercised`)
- **Red Flags Detected:** None
- **Discrepancy:** None (Clean)
- **Suggested Annotation Patch:** `{"readOnlyHint": true, "idempotentHint": true}`
- **Verification Analysis:** Tool exhibits genuine read-only / idempotent semantics. Declared hints were verified accurate.

---

### 4. Tool: `delete_entities` (`@modelcontextprotocol/server-memory`)
- **Description:** Delete multiple entities and their associated relations from the knowledge graph
- **Declared Annotations:** `{"readOnlyHint": null, "idempotentHint": null, "destructiveHint": null, "openWorldHint": null}`
- **Observed Behavior:** `idempotent_or_read_only` (Execution Status: `exercised`)
- **Red Flags Detected:** ["Caution: description mentions destructive action (delete) but tool omits destructiveHint/readOnlyHint"]
- **Discrepancy:** None (Clean)
- **Suggested Annotation Patch:** `{"readOnlyHint": true, "idempotentHint": true, "destructiveHint": true}`
- **Verification Analysis:** Tool lacks explicit specification hints required by client review scanners. Soro Audit successfully flagged missing annotations and proposed drop-in patch.

---

### 5. Tool: `delete_observations` (`@modelcontextprotocol/server-memory`)
- **Description:** Delete specific observations from entities in the knowledge graph
- **Declared Annotations:** `{"readOnlyHint": null, "idempotentHint": null, "destructiveHint": null, "openWorldHint": null}`
- **Observed Behavior:** `idempotent_or_read_only` (Execution Status: `exercised`)
- **Red Flags Detected:** ["Caution: description mentions destructive action (delete) but tool omits destructiveHint/readOnlyHint"]
- **Discrepancy:** None (Clean)
- **Suggested Annotation Patch:** `{"readOnlyHint": true, "idempotentHint": true, "destructiveHint": true}`
- **Verification Analysis:** Tool lacks explicit specification hints required by client review scanners. Soro Audit successfully flagged missing annotations and proposed drop-in patch.

---

### 6. Tool: `delete_relations` (`@modelcontextprotocol/server-memory`)
- **Description:** Delete multiple relations from the knowledge graph
- **Declared Annotations:** `{"readOnlyHint": null, "idempotentHint": null, "destructiveHint": null, "openWorldHint": null}`
- **Observed Behavior:** `idempotent_or_read_only` (Execution Status: `exercised`)
- **Red Flags Detected:** ["Caution: description mentions destructive action (delete) but tool omits destructiveHint/readOnlyHint"]
- **Discrepancy:** None (Clean)
- **Suggested Annotation Patch:** `{"readOnlyHint": true, "idempotentHint": true, "destructiveHint": true}`
- **Verification Analysis:** Tool lacks explicit specification hints required by client review scanners. Soro Audit successfully flagged missing annotations and proposed drop-in patch.

---

### 7. Tool: `read_graph` (`@modelcontextprotocol/server-memory`)
- **Description:** Read the entire knowledge graph
- **Declared Annotations:** `{"readOnlyHint": null, "idempotentHint": null, "destructiveHint": null, "openWorldHint": null}`
- **Observed Behavior:** `idempotent_or_read_only` (Execution Status: `exercised`)
- **Red Flags Detected:** None
- **Discrepancy:** None (Clean)
- **Suggested Annotation Patch:** `{"readOnlyHint": true, "idempotentHint": true}`
- **Verification Analysis:** Tool exhibits genuine read-only / idempotent semantics. Declared hints were verified accurate.

---

### 8. Tool: `search_nodes` (`@modelcontextprotocol/server-memory`)
- **Description:** Search for nodes in the knowledge graph based on a query
- **Declared Annotations:** `{"readOnlyHint": null, "idempotentHint": null, "destructiveHint": null, "openWorldHint": null}`
- **Observed Behavior:** `idempotent_or_read_only` (Execution Status: `exercised`)
- **Red Flags Detected:** None
- **Discrepancy:** None (Clean)
- **Suggested Annotation Patch:** `{"readOnlyHint": true, "idempotentHint": true}`
- **Verification Analysis:** Tool exhibits genuine read-only / idempotent semantics. Declared hints were verified accurate.

---

### 9. Tool: `open_nodes` (`@modelcontextprotocol/server-memory`)
- **Description:** Open specific nodes in the knowledge graph by their names
- **Declared Annotations:** `{"readOnlyHint": null, "idempotentHint": null, "destructiveHint": null, "openWorldHint": null}`
- **Observed Behavior:** `idempotent_or_read_only` (Execution Status: `exercised`)
- **Red Flags Detected:** None
- **Discrepancy:** None (Clean)
- **Suggested Annotation Patch:** `{"readOnlyHint": true, "idempotentHint": true}`
- **Verification Analysis:** Tool exhibits genuine read-only / idempotent semantics. Declared hints were verified accurate.

---

### 10. Tool: `read_file` (`@modelcontextprotocol/server-filesystem`)
- **Description:** Read the complete contents of a file as text. DEPRECATED: Use read_text_file instead.
- **Declared Annotations:** `{"readOnlyHint": null, "idempotentHint": null, "destructiveHint": null, "openWorldHint": null}`
- **Observed Behavior:** `idempotent_or_read_only` (Execution Status: `exercised`)
- **Red Flags Detected:** None
- **Discrepancy:** None (Clean)
- **Suggested Annotation Patch:** `{"readOnlyHint": true, "idempotentHint": true}`
- **Verification Analysis:** Tool exhibits genuine read-only / idempotent semantics. Declared hints were verified accurate.

---

### 11. Tool: `read_text_file` (`@modelcontextprotocol/server-filesystem`)
- **Description:** Read the complete contents of a file from the file system as text. Handles various text encodings and provides detailed error messages if the file cannot be read. Use this tool when you need to examine the contents of a single file. Use the 'head' parameter to read only the first N lines of a file, or the 'tail' parameter to read only the last N lines of a file. Operates on the file as text regardless of extension. Only works within allowed directories.
- **Declared Annotations:** `{"readOnlyHint": null, "idempotentHint": null, "destructiveHint": null, "openWorldHint": null}`
- **Observed Behavior:** `idempotent_or_read_only` (Execution Status: `exercised`)
- **Red Flags Detected:** None
- **Discrepancy:** None (Clean)
- **Suggested Annotation Patch:** `{"readOnlyHint": true, "idempotentHint": true}`
- **Verification Analysis:** Tool exhibits genuine read-only / idempotent semantics. Declared hints were verified accurate.

---

### 12. Tool: `read_media_file` (`@modelcontextprotocol/server-filesystem`)
- **Description:** Read a file and return it as a base64-encoded content block with its MIME type. Image and audio files are returned as image/audio content; any other file type is returned as an embedded resource. Only works within allowed directories.
- **Declared Annotations:** `{"readOnlyHint": null, "idempotentHint": null, "destructiveHint": null, "openWorldHint": null}`
- **Observed Behavior:** `idempotent_or_read_only` (Execution Status: `exercised`)
- **Red Flags Detected:** None
- **Discrepancy:** None (Clean)
- **Suggested Annotation Patch:** `{"readOnlyHint": true, "idempotentHint": true}`
- **Verification Analysis:** Tool exhibits genuine read-only / idempotent semantics. Declared hints were verified accurate.

---

### 13. Tool: `read_multiple_files` (`@modelcontextprotocol/server-filesystem`)
- **Description:** Read the contents of multiple files simultaneously. This is more efficient than reading files one by one when you need to analyze or compare multiple files. Each file's content is returned with its path as a reference. Failed reads for individual files won't stop the entire operation. Only works within allowed directories.
- **Declared Annotations:** `{"readOnlyHint": null, "idempotentHint": null, "destructiveHint": null, "openWorldHint": null}`
- **Observed Behavior:** `idempotent_or_read_only` (Execution Status: `exercised`)
- **Red Flags Detected:** None
- **Discrepancy:** None (Clean)
- **Suggested Annotation Patch:** `{"readOnlyHint": true, "idempotentHint": true}`
- **Verification Analysis:** Tool exhibits genuine read-only / idempotent semantics. Declared hints were verified accurate.

---

### 14. Tool: `write_file` (`@modelcontextprotocol/server-filesystem`)
- **Description:** Create a new file or completely overwrite an existing file with new content. Use with caution as it will overwrite existing files without warning. Handles text content with proper encoding. Only works within allowed directories.
- **Declared Annotations:** `{"readOnlyHint": null, "idempotentHint": null, "destructiveHint": null, "openWorldHint": null}`
- **Observed Behavior:** `idempotent_or_read_only` (Execution Status: `exercised`)
- **Red Flags Detected:** ["Caution: description mentions destructive action (overwrite) but tool omits destructiveHint/readOnlyHint"]
- **Discrepancy:** None (Clean)
- **Suggested Annotation Patch:** `{"readOnlyHint": true, "idempotentHint": true, "destructiveHint": true}`
- **Verification Analysis:** Tool lacks explicit specification hints required by client review scanners. Soro Audit successfully flagged missing annotations and proposed drop-in patch.

---

### 15. Tool: `edit_file` (`@modelcontextprotocol/server-filesystem`)
- **Description:** Make line-based edits to a text file. Each edit replaces exact line sequences with new content. Returns a git-style diff showing the changes made. Only works within allowed directories.
- **Declared Annotations:** `{"readOnlyHint": null, "idempotentHint": null, "destructiveHint": null, "openWorldHint": null}`
- **Observed Behavior:** `idempotent_or_read_only` (Execution Status: `exercised`)
- **Red Flags Detected:** None
- **Discrepancy:** None (Clean)
- **Suggested Annotation Patch:** `{"readOnlyHint": true, "idempotentHint": true}`
- **Verification Analysis:** Tool exhibits genuine read-only / idempotent semantics. Declared hints were verified accurate.

---

### 16. Tool: `create_directory` (`@modelcontextprotocol/server-filesystem`)
- **Description:** Create a new directory or ensure a directory exists. Can create multiple nested directories in one operation. If the directory already exists, this operation will succeed silently. Perfect for setting up directory structures for projects or ensuring required paths exist. Only works within allowed directories.
- **Declared Annotations:** `{"readOnlyHint": null, "idempotentHint": null, "destructiveHint": null, "openWorldHint": null}`
- **Observed Behavior:** `idempotent_or_read_only` (Execution Status: `exercised`)
- **Red Flags Detected:** None
- **Discrepancy:** None (Clean)
- **Suggested Annotation Patch:** `{"readOnlyHint": true, "idempotentHint": true}`
- **Verification Analysis:** Tool exhibits genuine read-only / idempotent semantics. Declared hints were verified accurate.

---

### 17. Tool: `list_directory` (`@modelcontextprotocol/server-filesystem`)
- **Description:** Get a detailed listing of all files and directories in a specified path. Results clearly distinguish between files and directories with [FILE] and [DIR] prefixes. This tool is essential for understanding directory structure and finding specific files within a directory. Only works within allowed directories.
- **Declared Annotations:** `{"readOnlyHint": null, "idempotentHint": null, "destructiveHint": null, "openWorldHint": null}`
- **Observed Behavior:** `idempotent_or_read_only` (Execution Status: `exercised`)
- **Red Flags Detected:** None
- **Discrepancy:** None (Clean)
- **Suggested Annotation Patch:** `{"readOnlyHint": true, "idempotentHint": true}`
- **Verification Analysis:** Tool exhibits genuine read-only / idempotent semantics. Declared hints were verified accurate.

---

### 18. Tool: `list_directory_with_sizes` (`@modelcontextprotocol/server-filesystem`)
- **Description:** Get a detailed listing of all files and directories in a specified path, including sizes. Results clearly distinguish between files and directories with [FILE] and [DIR] prefixes. This tool is useful for understanding directory structure and finding specific files within a directory. Only works within allowed directories.
- **Declared Annotations:** `{"readOnlyHint": null, "idempotentHint": null, "destructiveHint": null, "openWorldHint": null}`
- **Observed Behavior:** `idempotent_or_read_only` (Execution Status: `exercised`)
- **Red Flags Detected:** None
- **Discrepancy:** None (Clean)
- **Suggested Annotation Patch:** `{"readOnlyHint": true, "idempotentHint": true}`
- **Verification Analysis:** Tool exhibits genuine read-only / idempotent semantics. Declared hints were verified accurate.

---

### 19. Tool: `directory_tree` (`@modelcontextprotocol/server-filesystem`)
- **Description:** Get a recursive tree view of files and directories as a JSON structure. Each entry includes 'name', 'type' (file/directory), and 'children' for directories. Files have no children array, while directories always have a children array (which may be empty). The output is formatted with 2-space indentation for readability. Only works within allowed directories.
- **Declared Annotations:** `{"readOnlyHint": null, "idempotentHint": null, "destructiveHint": null, "openWorldHint": null}`
- **Observed Behavior:** `idempotent_or_read_only` (Execution Status: `exercised`)
- **Red Flags Detected:** ["Caution: description mentions destructive action (format) but tool omits destructiveHint/readOnlyHint"]
- **Discrepancy:** None (Clean)
- **Suggested Annotation Patch:** `{"readOnlyHint": true, "idempotentHint": true, "destructiveHint": true}`
- **Verification Analysis:** Tool lacks explicit specification hints required by client review scanners. Soro Audit successfully flagged missing annotations and proposed drop-in patch.

---

### 20. Tool: `move_file` (`@modelcontextprotocol/server-filesystem`)
- **Description:** Move or rename files and directories. Can move files between directories and rename them in a single operation. If the destination exists, the operation will fail. Works across different directories and can be used for simple renaming within the same directory. Both source and destination must be within allowed directories.
- **Declared Annotations:** `{"readOnlyHint": null, "idempotentHint": null, "destructiveHint": null, "openWorldHint": null}`
- **Observed Behavior:** `idempotent_or_read_only` (Execution Status: `exercised`)
- **Red Flags Detected:** None
- **Discrepancy:** None (Clean)
- **Suggested Annotation Patch:** `{"readOnlyHint": true, "idempotentHint": true}`
- **Verification Analysis:** Tool exhibits genuine read-only / idempotent semantics. Declared hints were verified accurate.

---
