"""Policy receipt and scoring checks runnable without extraction dependencies.

python tests/unit/test_topic_policy_experiment.py
"""

import base64
import gzip
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "probe_topic_quality.py"
SPEC = importlib.util.spec_from_file_location("topic_policy_experiment", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
experiment = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(experiment)


def report(*, precision: float = 0.8, recall: float = 0.7,
           empty: list[str] | None = None, passed: bool = True) -> dict[str, Any]:
    return {"metrics": {"yake": {"precision": precision, "recall": recall}},
            "minimum_precision": 0.5, "minimum_recall": 0.6,
            "empty_case_predictions": {"empty": [] if empty is None else empty},
            "passed": passed}


def note(identifier: str, classification: str, expected: list[list[str]],
         acceptable: list[str]) -> dict[str, Any]:
    return {"id": identifier, "source_path": f"{identifier}.md",
            "classification": classification, "expected": expected, "acceptable": acceptable}


class TopicPolicyExperimentTests(unittest.TestCase):
    def test_all_128_policies_share_exact_cached_proposals_without_mutable_aliases(self) -> None:
        calls = []

        class Extractor:
            def extract_keywords(self, text: str, /) -> list[tuple[str, float]]:
                calls.append(text)
                return [(text, 0.25), ("secondary", 0.75)]

        cache = experiment.ProposalCache(Extractor)
        observed = []
        policies = experiment.all_policies()
        self.assertEqual(len(policies), 128)
        self.assertEqual(len({experiment.policy_name(policy) for policy in policies}), 128)
        for _policy in policies:
            proposals = cache.extract_keywords("identical prose")
            observed.append(tuple(proposals))
            proposals.clear()
        self.assertEqual(calls, ["identical prose"])
        self.assertEqual(len(set(observed)), 1)
        self.assertEqual(experiment.policy_name(policies[0]), "clean-yake")
        self.assertEqual(experiment.policy_name(policies[-1]), "local-full")

    def test_grammar_cache_includes_structural_boundaries(self) -> None:
        cache = experiment.GrammarCache(lambda prose, edges: object())
        self.assertIs(cache("alpha beta", (5,)), cache("alpha beta", (5,)))
        self.assertIsNot(cache("alpha beta", (5,)), cache("alpha beta", ()))
        self.assertIsNot(cache("alpha beta", (5,)), cache("other prose", (5,)))

    def test_actual_policy_adapter_reuses_the_same_proposal_source_for_every_switch(self) -> None:
        observed = []
        calls = []

        class Extractor:
            def extract_keywords(self, text: str, /) -> list[tuple[str, float]]:
                calls.append(text)
                return [(text, 0.1)]

        def analyze(content: str, extractor: Any, **options: Any) -> Any:
            observed.append((id(extractor), extractor.extract_keywords(content)))
            return object()

        runner = experiment.PolicyRunner.__new__(experiment.PolicyRunner)
        runner.selection = SimpleNamespace(analyze_topics=analyze,
                                           SelectionPolicy=lambda **policy: policy)
        runner.proposals = experiment.ProposalCache(Extractor)
        runner.local = experiment.GrammarCache(lambda *args: object())
        runner.legacy = experiment.GrammarCache(lambda *args: object())
        for policy in experiment.all_policies():
            runner.explanation("same source", policy)
        self.assertEqual(len(observed), 128)
        self.assertEqual(calls, ["same source"])
        self.assertEqual(len({identifier for identifier, _ in observed}), 1)
        self.assertTrue(all(proposals == [("same source", 0.1)] for _, proposals in observed))

    def test_viability_checks_every_floor_empty_counts_and_frozen_contracts(self) -> None:
        legacy = {"a": report(empty=["old-noise"]), "b": report()}
        candidate = {"a": report(empty=["different-noise"], passed=False), "b": report()}
        # Preserving an old failure is eligible, but never turns its delivery gate green.
        self.assertEqual(experiment.viability(candidate, legacy), [])
        self.assertFalse(candidate["a"]["passed"])
        candidate["a"] = report(empty=["old-noise", "new-noise"])
        candidate["b"] = report(precision=0.49, recall=0.59)
        self.assertEqual(experiment.viability(candidate, legacy, ["known-answer"]), [
            "frozen_contract:known-answer", "a:additional_empty_case_labels",
            "b:precision_floor", "b:recall_floor"])

    def test_selection_uses_complexity_grammar_predicate_then_worst_metrics(self) -> None:
        policies = experiment.all_policies()
        reports = {experiment.policy_name(policy): {"set": report()} for policy in policies}
        reports["legacy"] = {"set": report()}
        contracts = {name: ["blocked"] for name in reports}
        grammar = dict.fromkeys(experiment.RULES, False)
        grammar["grammar"] = True
        predicate = dict.fromkeys(experiment.RULES, False)
        predicate["predicate_penalty"] = True
        simple = dict.fromkeys(experiment.RULES, False)
        simple["heading_prior"] = True
        for policy in [grammar, predicate, simple]:
            contracts[experiment.policy_name(policy)] = []
        chosen = experiment.select_policy(reports, policies[-1], contracts)
        self.assertEqual(chosen["selected_policy"], simple)
        no_rules = policies[0]
        contracts["clean-yake"] = []
        self.assertEqual(experiment.select_policy(reports, policies[-1], contracts)[
            "selected_policy"], no_rules)
        # Macro averages cannot hide a weaker fixture in the tie break.
        alternate = dict(simple, heading_prior=False, link_prior=True)
        self.assertLess(experiment.rank_policy(simple, {"a": report(precision=0.7),
                                                       "b": report(precision=0.7)}),
                        experiment.rank_policy(alternate, {"a": report(precision=1.0),
                                                          "b": report(precision=0.6)}))

    def test_no_viable_policy_retains_previous_without_lowering_floors(self) -> None:
        reports = {experiment.policy_name(policy): {"set": report(precision=0.1)}
                   for policy in experiment.all_policies()}
        reports["legacy"] = {"set": report()}
        contracts = {name: [] for name in reports}
        previous = experiment.all_policies()[-1]
        chosen = experiment.select_policy(reports, previous, contracts)
        self.assertEqual(chosen["selected_policy"], previous)
        self.assertFalse(chosen["simplification_succeeded"])
        self.assertEqual(chosen["eligible_policy_names"], [])
        self.assertTrue(chosen["selected_policy_is_diagnostic_only"])
        self.assertEqual(chosen["selection_outcome"],
                         "no_eligible_local_policy_keep_published_implementation")

    def test_holdout_keeps_underspecified_predictions_and_empty_failure_visible(self) -> None:
        gold = {"limit": 5, "minimum_precision": 0.5, "minimum_recall": 0.6, "notes": [
            note("subject", "substantive", [["alpha"]], ["alpha"]),
            note("uncertain", "underspecified", [], []),
            note("stub", "empty", [], []),
        ]}
        predictions = {"subject": ["alpha"], "uncertain": ["ambiguous"], "stub": ["noise"]}
        result = experiment.score_holdout(gold, predictions, str.casefold)
        self.assertEqual(result["metrics"], {"precision": 1.0, "recall": 1.0})
        self.assertEqual(len(result["cases"]), 3)
        self.assertEqual(result["underspecified"]["assigned_labels"], 1)
        self.assertEqual(result["underspecified"]["cases"][0]["predictions"], ["ambiguous"])
        self.assertEqual(result["hard_empty_false_positives"], [
            {"id": "stub", "labels": ["noise"], "false_positive_count": 1}])
        self.assertFalse(result["passed"])
        del predictions["uncertain"]
        with self.assertRaisesRegex(ValueError, "every case"):
            experiment.score_holdout(gold, predictions, str.casefold)

    def test_label_budget_ceiling_cannot_assume_one_label_per_group(self) -> None:
        self.assertEqual(experiment.budget_recall_ceiling([[str(i)] for i in range(8)]), 5 / 8)
        self.assertEqual(experiment.budget_recall_ceiling([["shared"], ["shared"]], 1), 1.0)
        self.assertIsNone(experiment.budget_recall_ceiling([]))

    def test_one_prediction_can_cover_two_groups_and_changes_five_label_ceiling(self) -> None:
        overlapping = [["shared", "alpha"], ["shared", "beta"]]
        gold = {"limit": 5, "minimum_precision": 1.0, "minimum_recall": 1.0,
                "notes": [note("subject", "substantive", overlapping, ["shared"])]}
        scored = experiment.score_holdout(gold, {"subject": ["shared"]}, str.casefold)
        self.assertEqual(scored["metrics"], {"precision": 1.0, "recall": 1.0})
        self.assertEqual(scored["cases"][0]["maximum_recall_at_label_budget"], 1.0)
        eight_groups = [*overlapping, *[[str(index)] for index in range(6)]]
        # Five labels can cover six groups, so the disjoint-group shortcut is wrong.
        self.assertEqual(experiment.budget_recall_ceiling(eight_groups, 5), 6 / 8)

    def test_all_source_checksums_verified_even_for_underspecified_case(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = b"ambiguous source"
            (root / "uncertain.md").write_bytes(raw)
            selected = {"id": "uncertain", "source_path": "uncertain.md",
                        "source_sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw),
                        "source_git_blob": hashlib.sha1(
                            b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()}
            manifest = {"source_commit": experiment.PINNED_LYT, "notes": [selected]}
            gold = {"notes": [dict(selected, classification="underspecified")]}
            self.assertEqual(experiment.verify_fresh_sources(
                manifest, gold, root, expected_count=1), {"uncertain": raw.decode()})
            (root / "uncertain.md").write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "Frozen source changed"):
                experiment.verify_fresh_sources(manifest, gold, root, expected_count=1)

    def test_source_manifest_identity_and_git_blob_are_checked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = b"alpha"
            (root / "alpha.md").write_bytes(raw)
            selected = {"id": "alpha", "source_path": "alpha.md",
                        "source_sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw),
                        "source_git_blob": "0" * 40}
            manifest = {"source_commit": experiment.PINNED_LYT, "notes": [selected]}
            gold = {"notes": [dict(selected, classification="substantive")]}
            with self.assertRaisesRegex(ValueError, "size/blob"):
                experiment.verify_fresh_sources(manifest, gold, root, expected_count=1)
            gold["notes"][0]["source_sha256"] = "wrong"
            with self.assertRaisesRegex(ValueError, "annotation source mismatch"):
                experiment.verify_fresh_sources(manifest, gold, root, expected_count=1)

    def test_archive_is_deterministic_ascii_and_round_trips_every_case(self) -> None:
        value = {"cases": [{"id": "underspecified", "predictions": ["café"]}]}
        lines = experiment.archive_lines(value)
        self.assertEqual(lines, experiment.archive_lines(value))
        self.assertTrue("\n".join(lines).isascii())
        metadata = json.loads(lines[1])
        raw = gzip.decompress(base64.b64decode("".join(lines[2:-1])))
        self.assertEqual(json.loads(raw), value)
        self.assertEqual(hashlib.sha256(raw).hexdigest(), metadata["sha256"])
        self.assertEqual(len(raw), metadata["bytes"])

    def test_holdout_cannot_read_fresh_data_before_policy_matches_selection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "selection.json"
            path.write_text(json.dumps({"format": experiment.FORMAT, "phase": "calibrate",
                                        "selected_policy": experiment.all_policies()[0]}))
            with patch.object(experiment.subprocess, "check_output") as git_show:
                with self.assertRaisesRegex(ValueError, "DEFAULT_POLICY"):
                    experiment.frozen_selection(path, experiment.all_policies()[-1])
                git_show.assert_not_called()

    def test_no_eligible_local_policy_cannot_be_promoted_to_holdout(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "selection.json"
            policy = experiment.all_policies()[-1]
            path.write_text(json.dumps({
                "format": experiment.FORMAT, "phase": "calibrate", "selected_policy": policy,
                "viable_policy_found": False,
                "selection_outcome": "no_eligible_local_policy_keep_published_implementation"}))
            with patch.object(experiment.subprocess, "check_output") as git_show:
                with self.assertRaisesRegex(ValueError, "ranked eligible"):
                    experiment.frozen_selection(path, policy)
                git_show.assert_not_called()

    def test_frozen_known_answer_function_is_called_and_its_globals_restored(self) -> None:
        namespace: dict[str, Any] = {"extract_topics": lambda _text: ["original"]}
        exec("def known_answer():\n    assert extract_topics('source') == ['original']\n",
             namespace)

        class Runner:
            def extract(self, content: str, policy: Any, **options: Any) -> list[str]:
                return ["changed"]

        original = namespace["extract_topics"]
        with patch.object(experiment.runpy, "run_path", return_value=namespace):
            failures = experiment.frozen_contracts(
                Runner(), experiment.all_policies()[0], legacy=False,
                functions={"existing_test.py": ["known_answer"]})
        self.assertEqual(failures, ["existing_test.py::known_answer"])
        self.assertIs(namespace["extract_topics"], original)

    def test_selection_logic_receipt_permits_only_default_binding_to_change(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "selection.py"
            path.write_text("DEFAULT_POLICY = Policy()\ndef choose():\n    return 1\n")
            original = experiment.selection_logic_sha256(path)
            path.write_text("DEFAULT_POLICY = Policy(grammar=False)\ndef choose():\n    return 1\n")
            self.assertEqual(experiment.selection_logic_sha256(path), original)
            path.write_text("DEFAULT_POLICY = Policy(grammar=False)\ndef choose():\n    return 2\n")
            self.assertNotEqual(experiment.selection_logic_sha256(path), original)


if __name__ == "__main__":
    unittest.main()
