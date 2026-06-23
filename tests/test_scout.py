"""Tests for Scout — evidence discovery (schema, safe_grep, coordinator)."""

from __future__ import annotations

from pathlib import Path

import pytest


class TestScoutPacketSchema:
    """Contract tests for the scout_packet.v1 JSON Schema."""

    def test_valid_packet_passes_schema_validation(self) -> None:
        """A well-formed scout packet passes Draft 2020-12 validation."""
        from forgerwrite_mcp.contracts.registry import ContractRegistry

        registry = ContractRegistry(
            Path(__file__).parent.parent / "schemas"
        )
        packet = {
            "schema_id": "forgewrite.scout_packet.v1",
            "question": "Find the error handler",
            "exact_evidence": [
                {"path": "src/error.rs", "line_start": 42, "finding": "handle_error()"}
            ],
        }
        # Should not raise
        registry.validate("scout_packet.v1.json", packet)

    def test_missing_exact_evidence_fails(self) -> None:
        """A packet without exact_evidence must fail validation."""
        from forgerwrite_mcp.contracts.registry import ContractRegistry, ContractValidationError

        registry = ContractRegistry(
            Path(__file__).parent.parent / "schemas"
        )
        packet = {
            "schema_id": "forgewrite.scout_packet.v1",
            "question": "Find the error handler",
        }
        with pytest.raises(ContractValidationError):
            registry.validate("scout_packet.v1.json", packet)

    def test_empty_question_fails(self) -> None:
        """A packet with empty question must fail validation."""
        from forgerwrite_mcp.contracts.registry import ContractRegistry, ContractValidationError

        registry = ContractRegistry(
            Path(__file__).parent.parent / "schemas"
        )
        packet = {
            "schema_id": "forgewrite.scout_packet.v1",
            "question": "",
            "exact_evidence": [],
        }
        with pytest.raises(ContractValidationError):
            registry.validate("scout_packet.v1.json", packet)

    def test_negative_line_start_fails(self) -> None:
        """Evidence with negative line_start must fail validation."""
        from forgerwrite_mcp.contracts.registry import ContractRegistry, ContractValidationError

        registry = ContractRegistry(
            Path(__file__).parent.parent / "schemas"
        )
        packet = {
            "schema_id": "forgewrite.scout_packet.v1",
            "question": "test",
            "exact_evidence": [
                {"path": "x.rs", "line_start": -1, "finding": "bad"}
            ],
        }
        with pytest.raises(ContractValidationError):
            registry.validate("scout_packet.v1.json", packet)

    def test_retrieval_hits_are_optional(self) -> None:
        """A packet without retrieval_hits is still valid."""
        from forgerwrite_mcp.contracts.registry import ContractRegistry

        registry = ContractRegistry(
            Path(__file__).parent.parent / "schemas"
        )
        packet = {
            "schema_id": "forgewrite.scout_packet.v1",
            "question": "test",
            "exact_evidence": [],
        }
        registry.validate("scout_packet.v1.json", packet)


class TestSafeGrep:
    """Tests for the safe_grep bounded grep utility."""

    def test_rejects_path_outside_repo(self) -> None:
        """safe_grep must reject queries that resolve outside the repo root."""
        from forgerwrite_mcp.errors import PublicError
        from forgerwrite_mcp.scout.safe_grep import safe_grep

        with pytest.raises(PublicError):
            safe_grep(Path("/tmp"), ["../../etc/passwd"])

    def test_rejects_absolute_path_in_query(self) -> None:
        """safe_grep must reject absolute paths in queries."""
        from forgerwrite_mcp.errors import PublicError
        from forgerwrite_mcp.scout.safe_grep import safe_grep

        with pytest.raises(PublicError):
            safe_grep(Path("/tmp"), ["/etc/passwd"])

    def test_skips_binary_files(self, tmp_path: Path) -> None:
        """safe_grep must not try to grep binary files."""
        from forgerwrite_mcp.scout.safe_grep import safe_grep

        # Create a file that looks binary by extension
        bin_file = tmp_path / "data.bin"
        bin_file.write_bytes(b"\x00\x01\x02\x03\x04\x05")
        text_file = tmp_path / "readme.txt"
        text_file.write_text("hello world\ntest line\n")

        result = safe_grep(tmp_path, ["test"])
        # Should find the match in readme.txt but not crash on data.bin
        assert len(result.matches) >= 1
        assert "readme.txt" in result.matches[0].path

    def test_respects_max_matches_per_query(self, tmp_path: Path) -> None:
        """safe_grep caps matches per query at max_matches_per_query."""
        from forgerwrite_mcp.scout.safe_grep import safe_grep

        # Create a file with many matching lines
        test_file = tmp_path / "big.txt"
        test_file.write_text("\n".join(f"line {i}: hello world" for i in range(100)))

        result = safe_grep(
            tmp_path,
            ["hello"],
            max_matches_per_query=5,
            max_total_matches=500,
            timeout_seconds=5.0,
        )
        assert len(result.matches) <= 5
        assert result.truncated is True

    def test_respects_max_total_matches(self, tmp_path: Path) -> None:
        """safe_grep caps total matches across all queries."""
        from forgerwrite_mcp.scout.safe_grep import safe_grep

        # Create files with many matching lines
        for i in range(3):
            f = tmp_path / f"file_{i}.txt"
            f.write_text("\n".join(f"line {j}: hello world" for j in range(50)))

        result = safe_grep(
            tmp_path,
            ["hello", "world"],
            max_matches_per_query=100,
            max_total_matches=10,
            timeout_seconds=5.0,
        )
        assert len(result.matches) <= 10

    def test_empty_queries_returns_empty(self) -> None:
        """safe_grep with empty queries returns empty result."""
        from forgerwrite_mcp.scout.safe_grep import safe_grep

        result = safe_grep(Path("/tmp"), [])
        assert result.matches == []
        assert result.truncated is False
        assert result.queries == 0

    def test_grep_finds_content_in_text_files(self, tmp_path: Path) -> None:
        """safe_grep finds matching lines in text files within the repo root."""
        from forgerwrite_mcp.scout.safe_grep import safe_grep

        # Create a temp file with known content
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello world\nfoo bar\nhello again\n")
        result = safe_grep(
            tmp_path,
            ["hello"],
            max_matches_per_query=10,
            max_total_matches=50,
        )
        assert len(result.matches) == 2
        assert result.matches[0].line_number == 1
        assert "hello" in result.matches[0].line_content


class TestScoutCoordinator:
    """Tests for the ScoutCoordinator — full evidence pipeline."""

    def test_produces_valid_packet(self, tmp_path: Path) -> None:
        """ScoutCoordinator produces a schema-valid ScoutPacket."""
        from forgerwrite_mcp.scout.coordinator import ScoutCoordinator

        # Create a small file
        test_file = tmp_path / "src" / "main.rs"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("fn handle_error() {}\nfn main() {}\n")

        coord = ScoutCoordinator(repo_root=tmp_path)
        packet = coord.scout(
            question="Find the error handler",
            allowed_files=["src/main.rs"],
        )
        assert packet.schema_id == "forgewrite.scout_packet.v1"
        assert len(packet.exact_evidence) >= 1
        assert "handle_error" in packet.exact_evidence[0]["finding"]

    def test_respects_evidence_caps(self, tmp_path: Path) -> None:
        """ScoutCoordinator caps exact_evidence at max_evidence_lines."""
        from forgerwrite_mcp.scout.coordinator import ScoutCoordinator

        # Create a file with many matching lines
        test_file = tmp_path / "src" / "big.rs"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("\n".join(f"fn func_{i}() {{}}" for i in range(500)))

        coord = ScoutCoordinator(
            repo_root=tmp_path,
            max_evidence_lines=20,
        )
        packet = coord.scout(
            question="Find all functions",
            allowed_files=["src/big.rs"],
        )
        assert len(packet.exact_evidence) <= 20

    def test_turbovec_fallback_when_disabled(self, tmp_path: Path) -> None:
        """Without an enricher, retrieval_hits should be empty, not crash."""
        from forgerwrite_mcp.scout.coordinator import ScoutCoordinator

        test_file = tmp_path / "src" / "main.rs"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("fn main() {}\n")

        coord = ScoutCoordinator(repo_root=tmp_path, enricher=None)
        packet = coord.scout(
            question="test",
            allowed_files=["src/main.rs"],
        )
        assert packet.retrieval_hits == []


class TestScoutPlanner:
    """Tests for the model-assisted query planner."""

    def test_planner_returns_list_of_queries(self) -> None:
        """Planner returns a list of query strings."""
        from forgerwrite_mcp.scout.planner import plan_queries

        queries = plan_queries("Find the error handler")
        assert isinstance(queries, list)
        assert len(queries) > 0
        assert all(isinstance(q, str) for q in queries)

    def test_planner_fallback_on_empty_question(self) -> None:
        """Planner returns empty list for empty question."""
        from forgerwrite_mcp.scout.planner import plan_queries

        queries = plan_queries("")
        assert queries == []

    def test_planner_limit_respected(self) -> None:
        """Planner respects max_queries limit."""
        from forgerwrite_mcp.scout.planner import plan_queries

        queries = plan_queries(
            "Find all error handlers and logging statements and async calls",
            max_queries=2,
        )
        assert len(queries) <= 2

    def test_planner_includes_fallback_when_model_fails(self) -> None:
        """When model returns invalid output, planner falls back to deterministic extraction."""
        from forgerwrite_mcp.scout.planner import plan_queries

        # A very long nonsensical question should still produce some queries via fallback
        queries = plan_queries("Fix the function that calculates the area of a circle")
        assert len(queries) >= 1
        # Fallback should include meaningful words
        assert any("area" in q.lower() or "circle" in q.lower() or "calculat" in q.lower() for q in queries)


class TestScoutSummarizer:
    """Tests for the evidence summarizer."""

    def test_summarizer_deduplicates_by_path_and_line(self) -> None:
        """Summarizer removes duplicate evidence entries."""
        from forgerwrite_mcp.scout.summarizer import summarize_evidence

        evidence = [
            {"path": "src/main.rs", "line_start": 10, "finding": "fn main()"},
            {"path": "src/main.rs", "line_start": 10, "finding": "fn main()"},
            {"path": "src/lib.rs", "line_start": 5, "finding": "fn helper()"},
        ]
        result = summarize_evidence(evidence)
        assert len(result) == 2

    def test_summarizer_caps_total(self) -> None:
        """Summarizer caps evidence at max_lines."""
        from forgerwrite_mcp.scout.summarizer import summarize_evidence

        evidence = [
            {"path": f"src/file_{i}.rs", "line_start": i, "finding": "fn func()"}
            for i in range(100)
        ]
        result = summarize_evidence(evidence, max_lines=10)
        assert len(result) <= 10

    def test_summarizer_sorts_by_path_then_line(self) -> None:
        """Summarizer sorts evidence by path then line_start."""
        from forgerwrite_mcp.scout.summarizer import summarize_evidence

        evidence = [
            {"path": "b.rs", "line_start": 5, "finding": "fn b()"},
            {"path": "a.rs", "line_start": 10, "finding": "fn a()"},
        ]
        result = summarize_evidence(evidence)
        assert result[0]["path"] == "a.rs"
        assert result[1]["path"] == "b.rs"

    def test_summarizer_empty_input(self) -> None:
        """Summarizer handles empty input gracefully."""
        from forgerwrite_mcp.scout.summarizer import summarize_evidence

        result = summarize_evidence([])
        assert result == []


class TestScoutCoordinatorModelAssisted:
    """Tests for the model-assisted path in ScoutCoordinator."""

    def test_scout_with_model_assisted_planner(self, tmp_path: Path) -> None:
        """ScoutCoordinator.scout() works with model-assisted planner enabled."""
        from forgerwrite_mcp.scout.coordinator import ScoutCoordinator

        test_file = tmp_path / "src" / "main.rs"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("fn handle_error() {}\nfn main() {}\n")

        coord = ScoutCoordinator(
            repo_root=tmp_path,
            use_model_planner=True,
        )
        packet = coord.scout(
            question="Find the error handler",
            allowed_files=["src/main.rs"],
        )
        # Should find evidence even with model planner (falls through to grep)
        assert len(packet.exact_evidence) >= 1
        assert "handle_error" in packet.exact_evidence[0]["finding"]
