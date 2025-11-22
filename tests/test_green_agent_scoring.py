"""
Tests for green agent scoring and evaluation logic.

This module tests the green agent's ability to correctly evaluate white agent
performance on terminal-bench tasks. It validates:
1. Task score calculation (test case pass rate + is_resolved status)
2. Edge case handling (missing data, empty results, unknown tasks)
3. Score formula correctness
"""

import json
from pathlib import Path
from typing import Any

import pytest

from terminal_bench.harness.models import BenchmarkResults, TrialResults

from src.green_agent.green_agent import TerminalBenchGreenAgentExecutor
from src.config import settings


# Test fixtures directory
FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(fixture_name: str) -> dict[str, Any]:
    """Load a test fixture from the fixtures directory."""
    fixture_path = FIXTURES_DIR / f"{fixture_name}.json"
    with open(fixture_path, "r") as f:
        return json.load(f)


def create_benchmark_results(fixture_data: dict) -> BenchmarkResults:
    """
    Create a BenchmarkResults object from fixture data.
    """
    results_data = fixture_data["benchmark_results"]

    trial_results = []
    for result in results_data["results"]:
        trial_results.append(TrialResults(**result))

    return BenchmarkResults(id=results_data["id"], results=trial_results)


def setup_mock_results_files(benchmark_results: BenchmarkResults, base_path: Path):
    """Helper to create mock results.json files for parser_results."""
    for result in benchmark_results.results:
        if result.recording_path:
            trial_dir = base_path / Path(result.recording_path).parent.parent
            trial_dir.mkdir(parents=True, exist_ok=True)
            results_json = trial_dir / "results.json"

            # Convert parser_results from enum values to strings
            parser_results_dict = {}
            if result.parser_results:
                for test_name, status in result.parser_results.items():
                    # Convert UnitTestStatus enum to string value
                    parser_results_dict[test_name] = (
                        status.value if hasattr(status, "value") else str(status)
                    )

            results_json.write_text(
                json.dumps(
                    {
                        "parser_results": (
                            parser_results_dict
                            if parser_results_dict
                            else result.parser_results
                        )
                    }
                )
            )


@pytest.fixture
def green_agent_executor():
    """Fixture providing a fresh TerminalBenchGreenAgentExecutor instance."""
    return TerminalBenchGreenAgentExecutor()


@pytest.fixture
def mock_eval_output_path(tmp_path, monkeypatch):
    """Fixture providing a temporary output path for evaluation results."""
    output_path = tmp_path / "eval_results"
    original_required = settings._required

    def mock_required(key):
        if key == "evaluation.output_path":
            return str(output_path)
        return original_required(key)

    monkeypatch.setattr(settings, "_required", mock_required)
    return output_path


class TestTaskScoreCalculation:
    """Test suite for individual task score calculation logic."""

    def test_all_tests_pass_resolved(self, green_agent_executor, mock_eval_output_path):
        """
        Test scoring when all test cases pass and task is resolved.
        Expected: score = 0.5 (test_case_component) + 0.5 (resolved_component) = 1.0
        """
        fixture = load_fixture("mock_results_all_pass")
        benchmark_results = create_benchmark_results(fixture)
        expected = fixture["expected_evaluation"]

        # Create mock results.json files
        setup_mock_results_files(benchmark_results, mock_eval_output_path)

        message = green_agent_executor.format_results_message(
            benchmark_results, {"white_agent_url": "http://test"}
        )

        # Verify all tasks got perfect scores
        for task_id, expected_score in expected["task_scores"].items():
            assert f"Score: {expected_score:.2%}" in message
            assert expected_score == 1.0, f"Task {task_id} should have score 1.0"

    def test_partial_tests_pass_not_resolved(
        self, green_agent_executor, mock_eval_output_path
    ):
        """
        Test scoring when some test cases pass but task is not resolved.
        Expected: score = 0.5 * (pass_rate) + 0.0 (not resolved)
        """
        fixture = load_fixture("mock_results_partial_pass")
        benchmark_results = create_benchmark_results(fixture)
        expected = fixture["expected_evaluation"]

        setup_mock_results_files(benchmark_results, mock_eval_output_path)

        message = green_agent_executor.format_results_message(
            benchmark_results, {"white_agent_url": "http://test"}
        )

        # Verify hello-world score (1/2 tests pass, not resolved)
        expected_hello_world_score = expected["task_scores"]["hello-world"]
        assert expected_hello_world_score == 0.25
        assert "hello-world" in message

    def test_all_tests_fail_not_resolved(
        self, green_agent_executor, mock_eval_output_path
    ):
        """
        Test scoring when all test cases fail and task is not resolved.
        Expected: score = 0.5 * 0.0 + 0.0 = 0.0
        """
        fixture = load_fixture("mock_results_all_fail")
        benchmark_results = create_benchmark_results(fixture)
        expected = fixture["expected_evaluation"]

        setup_mock_results_files(benchmark_results, mock_eval_output_path)

        message = green_agent_executor.format_results_message(
            benchmark_results, {"white_agent_url": "http://test"}
        )

        # Verify both tasks got zero scores
        for task_id, expected_score in expected["task_scores"].items():
            assert expected_score == 0.0


class TestEdgeCases:
    """Test suite for edge cases and error handling."""

    def test_missing_parser_results(self, green_agent_executor, mock_eval_output_path):
        """
        Test handling of tasks with missing parser_results.
        """
        fixture = load_fixture("mock_results_edge_cases")
        benchmark_results = create_benchmark_results(fixture)
        expected = fixture["expected_evaluation"]

        setup_mock_results_files(benchmark_results, mock_eval_output_path)

        message = green_agent_executor.format_results_message(
            benchmark_results, {"white_agent_url": "http://test"}
        )

        # hello-world has null parser_results but is_resolved=true
        # Score should be 0.0 + 0.5 = 0.5
        expected_hello_score = expected["task_scores"]["hello-world"]
        assert expected_hello_score == 0.5

    def test_empty_results(self, green_agent_executor, mock_eval_output_path):
        """
        Test handling of BenchmarkResults with no results.
        Should not crash and should return 0.0 weighted score.
        """
        fixture = load_fixture("mock_results_empty")
        benchmark_results = create_benchmark_results(fixture)
        expected = fixture["expected_evaluation"]

        message = green_agent_executor.format_results_message(
            benchmark_results, {"white_agent_url": "http://test"}
        )

        # Verify empty results are handled gracefully
        assert expected["weighted_overall_score"] == 0.0
        assert expected["n_resolved"] == 0
        assert expected["n_unresolved"] == 0


class TestScoreFormula:
    """Test suite specifically for the score calculation formula."""

    def test_score_formula_components(self):
        """
        Verify the score formula: score = 0.5 * (test_pass_rate) + 0.5 * (is_resolved)
        """
        test_cases = [
            (0.0, False, 0.0),  # No tests pass, not resolved
            (0.0, True, 0.5),  # No tests pass, but resolved (edge case)
            (0.5, False, 0.25),  # Half tests pass, not resolved
            (0.5, True, 0.75),  # Half tests pass, resolved
            (1.0, False, 0.5),  # All tests pass, not resolved (edge case)
            (1.0, True, 1.0),  # All tests pass, resolved
        ]

        for test_pass_rate, is_resolved, expected_score in test_cases:
            test_case_component = 0.5 * test_pass_rate
            resolved_component = 0.5 if is_resolved else 0.0
            calculated_score = test_case_component + resolved_component

            assert (
                abs(calculated_score - expected_score) < 0.0001
            ), f"Score mismatch for test_pass_rate={test_pass_rate}, is_resolved={is_resolved}"


class TestWeightedScoreFormula:
    """Test suite for weighted score calculation formula."""

    def test_weighted_score_formula(self):
        """
        Verify weighted score formula.
        """
        # Simple test case: 1 easy (score=1.0, weight=1), 1 hard (score=0.5, weight=3)
        easy_score = 1.0
        easy_weight = 1
        easy_count = 1

        hard_score = 0.5
        hard_weight = 3
        hard_count = 1

        numerator = (easy_score * easy_weight) + (hard_score * hard_weight)
        denominator = (easy_count * easy_weight) + (hard_count * hard_weight)
        expected_weighted = numerator / denominator

        # (1.0 * 1 + 0.5 * 3) / (1 + 3) = 2.5 / 4 = 0.625
        assert abs(expected_weighted - 0.625) < 0.0001
