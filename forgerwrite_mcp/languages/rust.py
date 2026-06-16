"""Rust language adapter — cargo-based validation commands."""

from __future__ import annotations


class RustAdapter:
    """Rust language defaults — cargo fmt, check, test, clippy."""

    language = "rust"

    def get_validation_commands(self) -> dict[str, str]:
        return {
            "fmt": "cargo fmt -- --check",
            "check": "cargo check",
            "test": "cargo test",
            "clippy": "cargo clippy --all-targets --all-features -- -D warnings",
        }

    def get_default_profile_name(self) -> str:
        return "rust_default"

    def get_profiles(self) -> dict[str, list[str]]:
        return {
            "rust_default": ["fmt", "check", "test", "clippy"],
        }
