# ForgeWrite Rust Knowledge Base

> Seed documents for the RAG index. Each `###` section is a self-contained
> retrieval unit. Split on `###` boundaries for embedding + indexing.
>
> Sources: rustc 1.91.1, Rust Edition 2024 Guide, cargo docs, clap v4, rand v0.8.
> Last updated: 2026-06-07.

---

## 1. Operation Templates

Every operation the model produces MUST follow these templates exactly.
The `content` field is mandatory for all operations except `delete_file`.

<!-- RAG-ID: op-template-create_file -->
### create_file — exact JSON template
```json
{
  "batch_id": "<unique-batch-id>",
  "slice_id": "<from-slice-contract>",
  "operations": [
    {
      "op": "create_file",
      "path": "src/lib.rs",
      "content": "pub fn add(a: i32, b: i32) -> i32 { a + b }\n"
    }
  ]
}
```
Rules: `path` must be in `allowed_files` from slice contract. Relative to repo root.
Parent directories created automatically. Do NOT include `start_line`, `end_line`,
`after_line`, or `before_line`.

<!-- RAG-ID: op-template-replace_file -->
### replace_file — exact JSON template
```json
{
  "batch_id": "<unique-batch-id>",
  "slice_id": "<from-slice-contract>",
  "operations": [
    {
      "op": "replace_file",
      "path": "src/main.rs",
      "content": "fn main() {\n    println!(\"hello\");\n}\n"
    }
  ]
}
```
Rules: Replaces the ENTIRE file content. Include complete new file. Target MUST exist.
Do NOT include line-number fields.

<!-- RAG-ID: op-template-replace_line_range -->
### replace_line_range — exact JSON template
```json
{
  "batch_id": "<unique-batch-id>",
  "slice_id": "<from-slice-contract>",
  "operations": [
    {
      "op": "replace_line_range",
      "path": "src/main.rs",
      "start_line": 3,
      "end_line": 5,
      "content": "    for i in 1..=5 {\n        println!(\"{}\", i);\n    }\n"
    }
  ]
}
```
Rules: `start_line` and `end_line` are 1-indexed and INCLUSIVE. Both required.
`content` required. Use line numbers from file context. Count blank lines.

<!-- RAG-ID: op-template-insert_after_line -->
### insert_after_line — exact JSON template
```json
{
  "batch_id": "<unique-batch-id>",
  "slice_id": "<from-slice-contract>",
  "operations": [
    {
      "op": "insert_after_line",
      "path": "src/main.rs",
      "after_line": 1,
      "content": "use std::io;\n"
    }
  ]
}
```
Rules: `after_line` is 1-indexed. Content appears AFTER this line.
`after_line: 0` inserts at beginning of file. `content` required.

<!-- RAG-ID: op-template-insert_before_line -->
### insert_before_line — exact JSON template
```json
{
  "batch_id": "<unique-batch-id>",
  "slice_id": "<from-slice-contract>",
  "operations": [
    {
      "op": "insert_before_line",
      "path": "src/main.rs",
      "before_line": 3,
      "content": "// Copyright notice\n"
    }
  ]
}
```
Rules: `before_line` is 1-indexed. Content appears BEFORE this line. `content` required.

<!-- RAG-ID: op-template-delete_file -->
### delete_file — exact JSON template
```json
{
  "batch_id": "<unique-batch-id>",
  "slice_id": "<from-slice-contract>",
  "operations": [
    {
      "op": "delete_file",
      "path": "src/old_module.rs"
    }
  ]
}
```
Rules: No `content` field needed. Target MUST exist. When recreating a file: use
`delete_file` FIRST, then `create_file` SECOND. Never create then delete.

---

## 2. Project Scaffolds

<!-- RAG-ID: scaffold-cargo-toml -->
### Cargo.toml — standard template
```toml
[package]
name = "<crate-name>"
version = "0.1.0"
edition = "2021"

[dependencies]
```
Rules: ALWAYS use `edition = "2021"`. Do NOT use `edition = "2024"` — the `gen`
keyword is reserved in 2024 and breaks `rand::Rng::gen()`. `[package]` before
`[dependencies]`. Crate name: lowercase, underscores OK, no hyphens.

<!-- RAG-ID: scaffold-lib-rs -->
### src/lib.rs — library root template
```rust
pub mod ops;
pub use ops::*;
```
Alternative for single-function library:
```rust
pub fn function_name(args) -> ReturnType {
    // implementation
}
```

<!-- RAG-ID: scaffold-main-rs -->
### src/main.rs — binary entry point template
```rust
fn main() {
    // entry point
}
```

<!-- RAG-ID: scaffold-full-project -->
### Full project scaffold — 5 files (create_file x5)
1. `Cargo.toml` — see scaffold above
2. `src/main.rs` — binary entry with `fn main()`
3. `src/lib.rs` — `pub mod X; pub use X::*;`
4. `src/ops.rs` — implementation functions
5. `tests/integration_test.rs` — `use <crate>::func; #[test] fn test() { ... }`

Use `create_file` for each. Include ALL 5 files in one batch.

---

## 3. Rust Rules & Conventions

<!-- RAG-ID: rust-import-rules -->
### Import and module rules
- `use` uses the CRATE NAME from `Cargo.toml` `[package] name`, NOT a made-up name.
  If `Cargo.toml` says `name = "calc"`, use `use calc::add;` — never `use calc_lib::add;`.
- `use` statements go at the top of the file, before any `fn` or `mod` declarations.
- Do NOT put `use` inside a function body.
- For items in the SAME crate, import from crate root: `use crate_name::item;`
- For test files in `tests/`, import by crate name: `use <crate>::*;`

<!-- RAG-ID: rust-edition-rules -->
### Edition rules (CRITICAL)
- ALWAYS use `edition = "2021"` in generated Cargo.toml. Edition 2024 reserves the
  `gen` keyword, which breaks `rand::Rng::gen()`. If the handoff says "2024", use
  "2021" instead — this is a known model-safe default.
- If edition 2024 is explicitly required, use `r#gen()` syntax: `rng.r#gen()`.

<!-- RAG-ID: rust-crate-naming -->
### Crate naming
- Crate names in Cargo.toml: lowercase with underscores: `my_project`
- In Rust source: imported with SAME name, hyphens → underscores: `use my_project::foo;`
- The lib crate in a project is ALWAYS the package name from Cargo.toml.
  There is NO automatic `_lib` suffix.

<!-- RAG-ID: rust-common-errors -->
### Common compile errors and fixes
| Error | Cause | Fix |
|-------|-------|-----|
| `unresolved import 'calc_lib'` | Used `_lib` suffix on crate name | Use exact name from Cargo.toml: `use calc::X;` |
| `expected identifier, found keyword 'gen'` | Edition 2024 reserves `gen` | Use edition 2021, or `r#gen()` |
| `cannot find value 'a' in this scope` | Variable shadowing in clap | Use enum variant: `Cli::Add { a, b } => add(a, b)` |
| `expected function, found Add` | Struct name shadows function | Use flat enum, not nested structs |
| `unresolved import 'rand::Rng'` | Missing trait import | Add `use rand::Rng;` |

---

## 4. Crate Usage Patterns

<!-- RAG-ID: crate-pattern-clap-v4 -->
### clap v4 — CLI with subcommands (enum pattern)
```rust
use clap::Parser;

#[derive(Parser)]
enum Cli {
    /// Add two numbers
    Add { a: i32, b: i32 },
    /// Subtract two numbers
    Sub { a: i32, b: i32 },
}

fn main() {
    let cli = Cli::parse();
    match cli {
        Cli::Add { a, b } => println!("{}", a + b),
        Cli::Sub { a, b } => println!("{}", a - b),
    }
}
```
Rules: Use `derive` feature: `clap = { version = "4", features = ["derive"] }`.
Use single enum with variants (NOT nested structs with `#[command(subcommand)]`).
Destructure variant fields directly in match arm. Do NOT create separate structs.

<!-- RAG-ID: crate-pattern-rand -->
### rand v0.8 — random number generation
```rust
use rand::Rng;

fn main() {
    let mut rng = rand::thread_rng();
    let n: u32 = rng.gen();
    println!("{}", n);
}
```
Rules: MUST `use rand::Rng;` — the `gen()` method comes from the `Rng` trait.
Use `rng.gen()` not `rand::random()`. For ranges: `rng.gen_range(0..100)`.

<!-- RAG-ID: crate-pattern-tests -->
### Test patterns
```rust
// In src/lib.rs or any src/*.rs file:
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_add() {
        assert_eq!(add(2, 3), 5);
    }
}
```
```rust
// In tests/integration_test.rs (external test):
use calc::add;

#[test]
fn test_add() {
    assert_eq!(add(2, 3), 5);
}
```
Rules: `#[cfg(test)]` module tests in same file as code. Integration tests in `tests/`
import crate by name. `use super::*` in `#[cfg(test)]` to access parent items.
`#[test]` required on every test function.

---

## 5. Fix Patterns (Repair Loop)

<!-- RAG-ID: fix-content-omission -->
### Fix: operation missing 'content' field
If validation says `'content' is a required property`, add the `content` field
with file contents as a string. Use `\n` for newlines. Every operation except
`delete_file` MUST have a `content` field.

Before: `{"op": "replace_file", "path": "src/main.rs"}`
After: `{"op": "replace_file", "path": "src/main.rs", "content": "fn main() {}\n"}`

<!-- RAG-ID: fix-wrong-crate-name -->
### Fix: unresolved import (wrong crate name)
Error: `unresolved import 'calc_lib'`
Fix: Change to exact crate name from Cargo.toml. If `name = "calc"`, use
`use calc::*;`. Never append `_lib`.

<!-- RAG-ID: fix-gen-keyword -->
### Fix: 'gen' keyword in edition 2024
Error: `expected identifier, found keyword 'gen'`
Fix: Change Cargo.toml edition to `"2021"`, or use `rng.r#gen()` in code.

<!-- RAG-ID: fix-test-assertion -->
### Fix: test assertion failure
Error: `assertion 'left == right' failed: left: 7, right: 6`
Fix: Change assertion to correct expected value.
Before: `assert_eq!(double(3), 7);`
After: `assert_eq!(double(3), 6);`
Look at actual values in error: `left` = code output, `right` = expected.
Fix assertion to match correct result.

<!-- RAG-ID: fix-clap-shadowing -->
### Fix: clap variable shadowing
Error: `expected function, found Add` or `cannot find value 'a' in this scope`
This happens with nested structs + `#[command(subcommand)]`. Fix: use flat enum.

WRONG:
```rust
struct Add { a: i32, b: i32 }
enum Commands { Add(Add) }
match cmd { Commands::Add(add) => add(a, b) } // ERROR: 'add' is struct
```
CORRECT:
```rust
enum Cli { Add { a: i32, b: i32 } }
match cli { Cli::Add { a, b } => add(a, b) } // OK
```

---

## 6. Operation Batch Structure

<!-- RAG-ID: schema-operation-batch -->
### Full operation batch structure
```json
{
  "batch_id": "<unique-string>",
  "slice_id": "<from-slice-contract>",
  "operations": [
    {
      "op": "<op-type>",
      "path": "<relative-path>",
      "content": "<file-or-insertion-content>"
    }
  ]
}
```
Required top-level fields: `batch_id`, `slice_id`, `operations` (non-empty array).
Each operation requires: `op` and `path`.
`content` required for: `create_file`, `replace_file`, `replace_line_range`,
`insert_after_line`, `insert_before_line`. NOT used for `delete_file`.

<!-- RAG-ID: rules-operation-ordering -->
### Operation ordering
- Operations applied IN ORDER (top to bottom).
- Delete + recreate: `delete_file` BEFORE `create_file`.
- Create + modify: `create_file` BEFORE `insert_*` / `replace_*`.
- Multiple ops on same file: account for line shifts from prior ops.

<!-- RAG-ID: rules-content-escaping -->
### Content escaping rules
- Content is a JSON string. Escape double quotes: `\"`
- Use `\n` for newlines (NOT actual newlines in JSON).
- Content field should be EXACT text written to file.
- Example: `"content": "fn main() {\n    println!(\"hello\");\n}\n"`

---

## 7. Quick Reference Card

<!-- RAG-ID: quickref-all-ops -->
### All operation types — quick reference
| op | Required fields | Use case |
|----|----------------|----------|
| `create_file` | op, path, content | New file, doesn't exist yet |
| `replace_file` | op, path, content | Overwrite entire existing file |
| `replace_line_range` | op, path, start_line, end_line, content | Replace specific lines |
| `insert_after_line` | op, path, after_line, content | Insert after a line |
| `insert_before_line` | op, path, before_line, content | Insert before a line |
| `delete_file` | op, path | Remove a file |
