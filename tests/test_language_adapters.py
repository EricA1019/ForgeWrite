"""Tests for the LanguageAdapter protocol and built-in adapters."""

from __future__ import annotations


class TestLanguageAdapterProtocol:
    """Contract tests for LanguageAdapter."""

    def test_adapter_is_runtime_checkable(self) -> None:
        """LanguageAdapter must be a runtime-checkable Protocol.

        Verify by checking that concrete adapters pass isinstance() against
        the Protocol class.
        """
        from forgerwrite_mcp.languages.base import LanguageAdapter
        from forgerwrite_mcp.languages.rust import RustAdapter

        adapter = RustAdapter()
        assert isinstance(adapter, LanguageAdapter)

    def test_adapter_exposes_language_property(self) -> None:
        """Every adapter must expose a 'language' string property."""
        from forgerwrite_mcp.languages.base import LanguageAdapter
        from forgerwrite_mcp.languages.python import PythonAdapter
        from forgerwrite_mcp.languages.rust import RustAdapter

        for cls in (RustAdapter, PythonAdapter):
            adapter = cls()
            assert isinstance(adapter, LanguageAdapter), f"{cls.__name__} does not implement LanguageAdapter"
            assert isinstance(adapter.language, str)
            assert len(adapter.language) > 0

    def test_adapter_exposes_validation_commands(self) -> None:
        """Every adapter must return a dict of command_id → shell command."""
        from forgerwrite_mcp.languages.python import PythonAdapter
        from forgerwrite_mcp.languages.rust import RustAdapter

        for cls in (RustAdapter, PythonAdapter):
            adapter = cls()
            commands = adapter.get_validation_commands()
            assert isinstance(commands, dict)
            assert len(commands) > 0
            for cmd_id, cmd_str in commands.items():
                assert isinstance(cmd_id, str)
                assert isinstance(cmd_str, str)
                assert len(cmd_id) > 0
                assert len(cmd_str) > 0

    def test_adapter_exposes_default_profile_name(self) -> None:
        """Every adapter must return a default validation profile name."""
        from forgerwrite_mcp.languages.python import PythonAdapter
        from forgerwrite_mcp.languages.rust import RustAdapter

        for cls in (RustAdapter, PythonAdapter):
            adapter = cls()
            profile_name = adapter.get_default_profile_name()
            assert isinstance(profile_name, str)
            assert len(profile_name) > 0

    def test_adapter_exposes_profiles(self) -> None:
        """Every adapter must return a dict of profile_id → command_id list."""
        from forgerwrite_mcp.languages.python import PythonAdapter
        from forgerwrite_mcp.languages.rust import RustAdapter

        for cls in (RustAdapter, PythonAdapter):
            adapter = cls()
            profiles = adapter.get_profiles()
            assert isinstance(profiles, dict)
            assert len(profiles) > 0
            for profile_id, cmd_ids in profiles.items():
                assert isinstance(profile_id, str)
                assert isinstance(cmd_ids, list)
                assert len(cmd_ids) > 0
                # Every command id in the profile must exist in validation commands
                for cmd_id in cmd_ids:
                    assert cmd_id in adapter.get_validation_commands(), (
                        f"{profile_id} references unknown command '{cmd_id}'"
                    )


class TestRustAdapter:
    """Rust adapter produces same defaults as current hardcoded behavior."""

    def test_rust_commands_match_current_config_template(self) -> None:
        """RustAdapter commands must match what init template currently hardcodes."""
        from forgerwrite_mcp.languages.rust import RustAdapter

        adapter = RustAdapter()
        commands = adapter.get_validation_commands()
        assert commands["fmt"] == "cargo fmt -- --check"
        assert commands["check"] == "cargo check"
        assert commands["test"] == "cargo test"
        assert "clippy" in commands

    def test_rust_default_profile_is_rust_default(self) -> None:
        """RustAdapter default profile name is 'rust_default'."""
        from forgerwrite_mcp.languages.rust import RustAdapter

        adapter = RustAdapter()
        assert adapter.get_default_profile_name() == "rust_default"

    def test_rust_profiles_reference_existing_commands(self) -> None:
        """Every command in rust_default profile exists in validation commands."""
        from forgerwrite_mcp.languages.rust import RustAdapter

        adapter = RustAdapter()
        commands = adapter.get_validation_commands()
        for profile_id, cmd_ids in adapter.get_profiles().items():
            assert profile_id == "rust_default"
            for cmd_id in cmd_ids:
                assert cmd_id in commands, f"Unknown command '{cmd_id}' in profile {profile_id}"


class TestPythonAdapter:
    """Python adapter for ruff/pytest/mypy profiles."""

    def test_python_commands_include_ruff_pytest_mypy(self) -> None:
        """PythonAdapter must include lint, format_check, test, typecheck."""
        from forgerwrite_mcp.languages.python import PythonAdapter

        adapter = PythonAdapter()
        commands = adapter.get_validation_commands()
        assert "lint" in commands
        assert "format_check" in commands
        assert "test" in commands
        assert "typecheck" in commands

    def test_python_default_profile(self) -> None:
        """PythonAdapter default profile is 'python_default' and includes all commands."""
        from forgerwrite_mcp.languages.python import PythonAdapter

        adapter = PythonAdapter()
        assert adapter.get_default_profile_name() == "python_default"
        profiles = adapter.get_profiles()
        assert "python_default" in profiles
        # The default profile should reference all known commands
        all_commands = set(adapter.get_validation_commands().keys())
        profile_commands = set(profiles["python_default"])
        assert profile_commands == all_commands, (
            f"python_default profile missing commands: {all_commands - profile_commands}"
        )

    def test_python_adapter_registers_in_discovery(self) -> None:
        """PythonAdapter is discoverable via get_adapter('python')."""
        from forgerwrite_mcp.languages import get_adapter, list_adapters

        adapters = list_adapters()
        assert "python" in adapters
        adapter = get_adapter("python")
        assert adapter is not None
        assert adapter.language == "python"


class TestAdapterDiscovery:
    """Tests for the adapter discovery system."""

    def test_get_adapter_returns_none_for_unknown(self) -> None:
        """get_adapter returns None for unsupported languages."""
        from forgerwrite_mcp.languages import get_adapter

        assert get_adapter("brainfuck") is None
        assert get_adapter("") is None

    def test_get_adapter_returns_rust_adapter(self) -> None:
        """get_adapter('rust') returns a RustAdapter."""
        from forgerwrite_mcp.languages import get_adapter
        from forgerwrite_mcp.languages.rust import RustAdapter

        adapter = get_adapter("rust")
        assert adapter is not None
        assert isinstance(adapter, RustAdapter)

    def test_list_adapters_includes_rust_and_python(self) -> None:
        """list_adapters returns both 'rust' and 'python'."""
        from forgerwrite_mcp.languages import list_adapters

        adapters = list_adapters()
        assert "rust" in adapters
        assert "python" in adapters
