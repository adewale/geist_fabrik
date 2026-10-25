"""Frozen factorial calibration and separately authorized held-out topic evaluation.

Calibration never opens fresh evidence. Holdout requires a committed calibration
receipt and its selected production policy before reading fresh sources. Helpers
and their tests use stdlib only; experiments require the locked dependencies.
"""

from __future__ import annotations

import argparse
import ast
import base64
import gzip
import hashlib
import itertools
import json
import runpy
import subprocess
from collections import Counter
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import asdict
from importlib.metadata import version
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Protocol
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
PINNED_LYT = "e191473fcb326df78cca8a6c49b29420ab318e46"
RULES = (
    "heading_prior",
    "link_prior",
    "predicate_penalty",
    "score_gap",
    "containment",
    "repeated_words",
    "grammar",
)
PLAN = Path("benchmarks/corpora/topic_policy_experiment.json")
CONTROLS = Path("benchmarks/corpora/topic_boilerplate_controls.json")
CALIBRATION = {
    "synthetic": Path("tests/fixtures/topic_gold.json"),
    "public-starter": Path("tests/fixtures/topic_real_gold.json"),
    "narrative": Path("benchmarks/corpora/topic_narrative_proxy_gold.json"),
    "lyt": Path("benchmarks/corpora/topic_lyt_proxy_gold.json"),
}
FORMAT = "geistfabrik-topic-policy-experiment-v1"
EVIDENCE_FORMAT = "geistfabrik-topic-evidence-v1"
LEGACY_COMPARATOR = {
    "label": "legacy selection/current safe grounding",
    "scope": "Historical selection rules and document-global grammar over the same current "
    "safe source grounding used by every policy; not the full historical engine.",
    "historical_engine_equivalence": False,
}
ARCHIVE_BEGIN = "TOPIC_POLICY_ARCHIVE_BEGIN"
ARCHIVE_END = "TOPIC_POLICY_ARCHIVE_END"


class KeywordSource(Protocol):
    def extract_keywords(self, text: str, /) -> list[tuple[str, float]]: ...


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2, allow_nan=False) + "\n"
    ).encode("ascii")


def all_policies() -> list[dict[str, bool]]:
    return [dict(zip(RULES, bits)) for bits in itertools.product((False, True), repeat=len(RULES))]


def policy_name(policy: Mapping[str, bool]) -> str:
    if not any(policy.values()):
        return "clean-yake"
    if all(policy.values()):
        return "local-full"
    return "+".join(rule for rule in RULES if policy[rule])


def validate_policy(policy: Any) -> dict[str, bool]:
    if not isinstance(policy, dict) or set(policy) != set(RULES):
        raise ValueError("Selection must specify exactly the seven frozen rules")
    if any(type(value) is not bool for value in policy.values()):
        raise ValueError("Policy switches must be booleans")
    return {rule: policy[rule] for rule in RULES}


class ProposalCache:
    """One real proposal computation per exact prose, independent of policy."""

    def __init__(self, factory: Callable[[], KeywordSource]) -> None:
        self.factory = factory
        self.proposals: dict[str, tuple[tuple[str, float], ...]] = {}

    def extract_keywords(self, text: str, /) -> list[tuple[str, float]]:
        if text not in self.proposals:
            self.proposals[text] = tuple(self.factory().extract_keywords(text))
        return list(self.proposals[text])


class GrammarCache:
    def __init__(self, factory: Callable[..., Any]) -> None:
        self.factory = factory
        self.instances: dict[tuple[str, tuple[int, ...]], Any] = {}

    def __call__(self, prose: str, boundaries: tuple[int, ...]) -> Any:
        key = prose, boundaries
        if key not in self.instances:
            self.instances[key] = self.factory(prose, boundaries)
        return self.instances[key]


def empty_case_labels(report: Mapping[str, Any]) -> int:
    return sum(len(labels) for labels in report["empty_case_predictions"].values())


def viability(
    reports: Mapping[str, Mapping[str, Any]],
    legacy: Mapping[str, Mapping[str, Any]],
    contract_failures: Sequence[str] = (),
) -> list[str]:
    """Non-regression eligibility does not waive any existing empty-case gate."""
    failures = [f"frozen_contract:{name}" for name in contract_failures]
    for name, report in reports.items():
        for metric in ("precision", "recall"):
            if report["metrics"]["yake"][metric] < report[f"minimum_{metric}"]:
                failures.append(f"{name}:{metric}_floor")
        if empty_case_labels(report) > empty_case_labels(legacy[name]):
            failures.append(f"{name}:additional_empty_case_labels")
    return failures


def rank_policy(
    policy: Mapping[str, bool],
    reports: Mapping[str, Mapping[str, Any]],
) -> tuple[int, bool, bool, float, float, str]:
    return (
        sum(policy.values()),
        policy["grammar"],
        policy["predicate_penalty"],
        -min(report["metrics"]["yake"]["precision"] for report in reports.values()),
        -min(report["metrics"]["yake"]["recall"] for report in reports.values()),
        policy_name(policy),
    )


def select_policy(
    reports: Mapping[str, Mapping[str, Any]],
    previous: Mapping[str, bool],
    contracts: Mapping[str, Sequence[str]],
) -> dict[str, Any]:
    eligible = []
    failures = {}
    for policy in all_policies():
        name = policy_name(policy)
        rejected = viability(reports[name], reports["legacy"], contracts[name])
        failures[name] = rejected
        if not rejected:
            eligible.append(policy)
    selected = (
        min(eligible, key=lambda policy: rank_policy(policy, reports[policy_name(policy)]))
        if eligible
        else dict(previous)
    )
    return {
        "selected_policy": selected,
        "selected_policy_name": policy_name(selected),
        "viable_policy_found": bool(eligible),
        "simplification_succeeded": bool(eligible)
        and sum(selected.values()) < sum(previous.values()),
        "selection_outcome": (
            "ranked_eligible_policy"
            if eligible
            else "no_eligible_local_policy_keep_published_implementation"
        ),
        "selected_policy_is_diagnostic_only": not bool(eligible),
        "eligible_policy_names": sorted(policy_name(policy) for policy in eligible),
        "viability_failures": failures,
    }


def verified_content(note: Mapping[str, Any], source_root: Path) -> str:
    if "source_path" not in note:
        return str(note["content"])
    source = (source_root / note["source_path"]).resolve()
    if not source.is_relative_to(source_root.resolve()):
        raise ValueError("Source must remain inside the pinned checkout")
    raw = source.read_bytes()
    if sha256(raw) != note["source_sha256"]:
        raise ValueError(f"Frozen source changed: {note['source_path']}")
    return raw.decode("utf-8")


def verify_fresh_sources(
    manifest: Mapping[str, Any],
    gold: Mapping[str, Any],
    source_root: Path,
    *,
    expected_count: int = 16,
) -> dict[str, str]:
    """Check every source, including underspecified/empty cases, before extraction."""
    if manifest["source_commit"] != PINNED_LYT:
        raise ValueError("Fresh manifest must bind the pinned LYT commit")
    selected = {note["id"]: note for note in manifest["notes"]}
    annotated = {note["id"]: note for note in gold["notes"]}
    if (
        len(selected) != expected_count
        or len(annotated) != expected_count
        or len(manifest["notes"]) != expected_count
        or len(gold["notes"]) != expected_count
        or selected.keys() != annotated.keys()
    ):
        raise ValueError("Fresh selection/annotations must retain every unique selected case")
    contents = {}
    for identifier, note in annotated.items():
        chosen = selected[identifier]
        if any(chosen[field] != note[field] for field in ("source_path", "source_sha256")):
            raise ValueError(f"Fresh annotation source mismatch: {identifier}")
        if note["classification"] not in {"substantive", "empty", "underspecified"}:
            raise ValueError(f"Unknown fresh classification: {identifier}")
        contents[identifier] = verified_content(note, source_root)
        raw = (source_root / chosen["source_path"]).read_bytes()
        blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
        if len(raw) != chosen["bytes"] or blob != chosen["source_git_blob"]:
            raise ValueError(f"Fresh source size/blob mismatch: {identifier}")
    return contents


def budget_recall_ceiling(expected: Sequence[Iterable[str]], limit: int = 5) -> float | None:
    """Maximum required-group coverage at the label budget, allowing shared aliases."""
    if not expected:
        return None
    aliases: dict[str, int] = {}
    for index, group in enumerate(expected):
        for alias in group:
            aliases[alias] = aliases.get(alias, 0) | (1 << index)
    masks = set(aliases.values())
    possible = {0}
    full = (1 << len(expected)) - 1
    for _ in range(limit):
        possible |= {existing | mask for existing in possible for mask in masks}
        if full in possible:
            return 1.0
    return max(mask.bit_count() for mask in possible) / len(expected)


def score_holdout(
    gold: Mapping[str, Any],
    predictions: Mapping[str, Sequence[str]],
    normalise: Callable[[str], str],
) -> dict[str, Any]:
    """Keep all predictions; uncertain annotations never enter substantive macro scores."""
    cases = []
    substantive = []
    underspecified = []
    hard_empty = []
    if gold["limit"] != 5:
        raise ValueError("Holdout must score every label at the fixed limit five")
    if set(predictions) != {note["id"] for note in gold["notes"]}:
        raise ValueError("Holdout predictions must cover every case exactly")
    for note in gold["notes"]:
        labels = list(predictions[note["id"]])
        if len(labels) > gold["limit"]:
            raise ValueError("Holdout prediction exceeds fixed label budget")
        expected = [{normalise(alias) for alias in group} for group in note["expected"]]
        acceptable = {normalise(label) for label in note["acceptable"]}
        precision = sum(label in acceptable for label in labels) / max(1, len(labels))
        recall = sum(bool(group.intersection(labels)) for group in expected) / max(1, len(expected))
        case = {
            "id": note["id"],
            "source_path": note["source_path"],
            "classification": note["classification"],
            "predictions": labels,
            "annotation_reason": note.get("reason"),
            "precision": precision,
            "recall": recall,
            "required_groups": len(expected),
            "maximum_recall_at_label_budget": budget_recall_ceiling(expected, gold["limit"]),
        }
        cases.append(case)
        if note["classification"] == "substantive":
            substantive.append(case)
        elif note["classification"] == "underspecified":
            underspecified.append(case)
        elif note["classification"] == "empty":
            hard_empty.append(
                {"id": note["id"], "labels": labels, "false_positive_count": len(labels)}
            )
        else:
            raise ValueError("Unknown holdout classification")
    metrics = {
        key: sum(case[key] for case in substantive) / max(1, len(substantive))
        for key in ("precision", "recall")
    }
    return {
        "cases": cases,
        "metrics": metrics,
        "substantive_cases": len(substantive),
        "cases_limited_by_label_budget": sum(
            case["maximum_recall_at_label_budget"] < 1 for case in substantive
        ),
        "maximum_macro_recall_at_label_budget": sum(
            case["maximum_recall_at_label_budget"] for case in substantive
        )
        / max(1, len(substantive)),
        "underspecified": {
            "cases": underspecified,
            "assigned_labels": sum(len(case["predictions"]) for case in underspecified),
        },
        "hard_empty_cases": hard_empty,
        "hard_empty_false_positives": [case for case in hard_empty if case["labels"]],
        "minimum_precision": gold["minimum_precision"],
        "minimum_recall": gold["minimum_recall"],
        "passed": bool(substantive)
        and metrics["precision"] >= gold["minimum_precision"]
        and metrics["recall"] >= gold["minimum_recall"]
        and not any(case["labels"] for case in hard_empty),
        "macro_scope": "substantive only; underspecified judgments reported separately",
    }


def archive_lines(report: Any) -> list[str]:
    raw = json_bytes(report)
    payload = base64.b64encode(gzip.compress(raw, compresslevel=9, mtime=0)).decode("ascii")
    header = json.dumps(
        {"format": FORMAT, "encoding": "gzip+base64", "bytes": len(raw), "sha256": sha256(raw)},
        sort_keys=True,
    )
    return [
        ARCHIVE_BEGIN,
        header,
        *(payload[i : i + 120] for i in range(0, len(payload), 120)),
        ARCHIVE_END,
    ]


def git(*arguments: str, root: Path = REPO) -> str:
    return subprocess.check_output(["git", *arguments], cwd=root, text=True).strip()


def validate_checkout(root: Path) -> None:
    if git("rev-parse", "HEAD", root=root) != PINNED_LYT:
        raise ValueError("LYT checkout must equal the frozen mirror commit")
    subprocess.run(["git", "diff", "--quiet", "HEAD", "--", "."], cwd=root, check=True)


def selection_logic_sha256(path: Path) -> str:
    """Permit only the chosen default binding to change after calibration."""
    tree = ast.parse(path.read_bytes())
    tree.body = [
        node
        for node in tree.body
        if not (
            isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "DEFAULT_POLICY"
                for target in node.targets
            )
            or isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "DEFAULT_POLICY"
        )
    ]
    return sha256(ast.dump(tree, include_attributes=False).encode())


def receipt() -> dict[str, Any]:
    from geistfabrik.topic_grammar import grammar_identity

    files = [
        PLAN,
        CONTROLS,
        Path("pyproject.toml"),
        Path("uv.lock"),
        Path("scripts/probe_topic_quality.py"),
        Path("scripts/topic_legacy_grammar.py"),
        Path("scripts/topic_evidence_archive.py"),
        Path("scripts/evaluate_topics.py"),
        Path("scripts/generate_narrative_corpus.py"),
        Path("scripts/generate_temporal_corpus.py"),
        *(
            Path("src/geistfabrik") / name
            for name in (
                "topic_selection.py",
                "topic_grammar.py",
                "topic_text.py",
                "markdown_parser.py",
            )
        ),
    ]
    plan = json.loads((REPO / PLAN).read_text())
    for functions in (
        plan["frozen_contract_functions"],
        plan["source_role_ablation"]["contract_functions"],
    ):
        files.extend(Path(filename) for filename in functions)
    files = list(dict.fromkeys(files))
    return {
        "measured_git_commit": git("rev-parse", "HEAD"),
        "tracked_diff_sha256": sha256(subprocess.check_output(["git", "diff", "HEAD"], cwd=REPO)),
        "file_sha256": {str(path): sha256((REPO / path).read_bytes()) for path in files},
        "dependency_versions": {
            name: version(name)
            for name in ("yake", "textblob", "nltk", "markdown-it-py", "scikit-learn")
        },
        "grammar_dependency_sha256": grammar_identity(),
        "lyt_commit": PINNED_LYT,
        "selection_logic_sha256": selection_logic_sha256(
            REPO / "src/geistfabrik/topic_selection.py"
        ),
    }


class PolicyRunner:
    def __init__(self) -> None:
        import yake

        from geistfabrik import topic_selection as selection
        from geistfabrik.topic_grammar import CandidateGrammar
        from scripts.topic_legacy_grammar import LegacyGrammar

        self.selection = selection
        self.proposals = ProposalCache(lambda: yake.KeywordExtractor(**selection.SETTINGS))
        self.local = GrammarCache(CandidateGrammar)
        self.legacy = GrammarCache(LegacyGrammar)
        self.summaries: dict[str, dict[str, Any]] = {}

    def explanation(
        self,
        content: str,
        policy: Mapping[str, bool],
        *,
        legacy: bool = False,
        extractor: KeywordSource | None = None,
    ) -> Any:
        return self.selection.analyze_topics(
            content,
            self.proposals if extractor is None else extractor,
            policy=self.selection.SelectionPolicy(**policy),
            grammar_factory=self.legacy if legacy else self.local,
        )

    def extract(
        self,
        content: str,
        policy: Mapping[str, bool],
        *,
        legacy: bool = False,
        extractor: KeywordSource | None = None,
    ) -> Any:
        explanation = self.explanation(content, policy, legacy=legacy, extractor=extractor)
        self.summaries[sha256(content.encode())] = {
            "reasons": dict(sorted(Counter(row.reason for row in explanation.candidates).items())),
            "adjustments": dict(
                sorted(
                    Counter(
                        change for row in explanation.candidates for change in row.adjustments
                    ).items()
                )
            ),
        }
        return explanation.topics


@contextmanager
def calibration_sources(lyt: Path) -> Iterator[dict[str, tuple[Path, Path]]]:
    from scripts.generate_narrative_corpus import generate_narrative_corpus
    from scripts.generate_temporal_corpus import apply_snapshot

    with TemporaryDirectory(prefix="topic-policy-calibration-") as directory:
        corpus = Path(directory) / "narrative-corpus"
        manifest = generate_narrative_corpus(corpus)
        narrative = Path(directory) / "narrative"
        for record in manifest["snapshots"]:
            apply_snapshot(corpus, narrative, record["index"])
        yield {
            name: (
                REPO / fixture,
                narrative if name == "narrative" else lyt if name == "lyt" else REPO,
            )
            for name, fixture in CALIBRATION.items()
        }


def frozen_contracts(
    runner: PolicyRunner,
    policy: Mapping[str, bool],
    *,
    legacy: bool,
    functions: Mapping[str, Sequence[str]],
) -> list[str]:
    failures = []
    for filename, names in functions.items():
        namespace = runpy.run_path(str(REPO / filename))
        for name in names:
            function = namespace[name]
            has_extractor = "extract_topics" in function.__globals__
            original = function.__globals__.get("extract_topics")

            def selected(content: str, extractor: KeywordSource | None = None) -> Any:
                return runner.extract(content, policy, legacy=legacy, extractor=extractor)

            if has_extractor:
                function.__globals__["extract_topics"] = selected
            try:
                function()
            except AssertionError:
                failures.append(f"{filename}::{name}")
            finally:
                if has_extractor:
                    function.__globals__["extract_topics"] = original
    return failures


@contextmanager
def source_role_runner(topic_text: Any, runner_factory: Callable[[], Any]) -> Iterator[Any]:
    """A different preprocessing arm must never reuse baseline projections/proposals."""
    topic_text._projection.cache_clear()
    try:
        with patch.object(topic_text, "_SECTION_LABELS", frozenset()):
            yield runner_factory()
    finally:
        # patch.object restores the role vocabulary before this final cache clear.
        topic_text._projection.cache_clear()


def source_role_ablation(
    plan: Mapping[str, Any],
    policy: Mapping[str, bool],
    fixtures: Mapping[str, tuple[Path, Path]],
    baseline_runner: PolicyRunner,
    legacy_reports: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Separate preprocessor experiment: it cannot enter the frozen 128-policy ranking."""
    from geistfabrik import topic_text
    from scripts import evaluate_topics as evaluation

    preregistered = plan["source_role_ablation"]
    role_functions = preregistered["contract_functions"]
    baseline_role_failures = frozen_contracts(
        baseline_runner, policy, legacy=False, functions=role_functions
    )
    reports = {}
    sources = {}
    with source_role_runner(topic_text, PolicyRunner) as runner:
        contract_failures = frozen_contracts(
            runner, policy, legacy=False, functions=plan["frozen_contract_functions"]
        )
        role_failures = frozen_contracts(runner, policy, legacy=False, functions=role_functions)
        for name, (fixture_path, source_root) in fixtures.items():
            gold = json.loads(fixture_path.read_text())
            contents = {note["id"]: verified_content(note, source_root) for note in gold["notes"]}
            empty_ids = {note["id"] for note in gold["notes"] if not note["expected"]}
            runner.summaries = {}

            def extract(content: str) -> Any:
                return runner.extract(content, policy)

            with patch.object(evaluation, "extract_topics", extract):
                report = evaluation.evaluate_gold(fixture_path, source_root=source_root)
            report["empty_case_predictions"] = {
                case["id"]: case["predictions"]["yake"]
                for case in report["cases"]
                if case["id"] in empty_ids
            }
            report["decision_summary"] = {
                identifier: runner.summaries.get(sha256(content.encode()), {})
                for identifier, content in contents.items()
            }
            reports[name] = report
            sources[name] = {
                identifier: {
                    "source_sha256": sha256(content.encode()),
                    "prose_sha256": sha256(topic_text.topic_prose(content).encode()),
                }
                for identifier, content in contents.items()
            }
        proposals = {
            sha256(prose.encode()): list(rows) for prose, rows in runner.proposals.proposals.items()
        }
    failures = viability(reports, legacy_reports, [*contract_failures, *role_failures])
    return {
        "name": "without-generic-section-role",
        "pre_registered_plan": preregistered,
        "pre_registered_plan_sha256": sha256(json_bytes(preregistered)),
        "policy": dict(policy),
        "baseline_policy_reference": policy_name(policy),
        "used_for_selection": False,
        "proposal_cache_isolated": True,
        "candidate_proposals_shared_with_factorial": False,
        "projection_cache_cleared_before_and_after": True,
        "proposal_difference_reason": "Disabling generic named section-role curation admits "
        "different prose before YAKE; candidate proposals are recomputed for this arm.",
        "reports": reports,
        "sources": sources,
        "yake_proposals": proposals,
        "frozen_contract_failures": contract_failures,
        "source_role_contract_failures": {"baseline": baseline_role_failures, "arm": role_failures},
        "diagnostic_failure_reasons": failures,
        "fixed_role_contract_blocks_selection": bool(role_failures),
        "empty_noise_blocks_selection": any(
            failure.endswith(":additional_empty_case_labels") for failure in failures
        ),
        "requires_selection_expansion_before_holdout": not failures and not baseline_role_failures,
        "justification_scope": "Fixed source-role regression contracts and calibration "
        "diagnostics; independent semantic usefulness of heading curation is not established.",
    }


def validate_source_role_receipt(report: Mapping[str, Any], plan: Mapping[str, Any]) -> None:
    """A source-role diagnostic that qualifies requires a new selection plan before holdout."""
    arm = report.get("source_role_ablation")
    preregistered = plan.get("source_role_ablation")
    if not isinstance(arm, dict) or not isinstance(preregistered, dict):
        raise ValueError("Frozen selection requires the preregistered source-role ablation")
    if (
        arm.get("name") != "without-generic-section-role"
        or arm.get("pre_registered_plan") != preregistered
        or arm.get("pre_registered_plan_sha256") != sha256(json_bytes(preregistered))
        or arm.get("policy") != report["selected_policy"]
        or arm.get("baseline_policy_reference") != policy_name(report["selected_policy"])
        or arm.get("used_for_selection") is not False
        or arm.get("proposal_cache_isolated") is not True
        or arm.get("candidate_proposals_shared_with_factorial") is not False
        or arm.get("projection_cache_cleared_before_and_after") is not True
        or set(arm.get("reports", {})) != set(CALIBRATION)
    ):
        raise ValueError("Frozen source-role ablation metadata changed or is incomplete")
    role_failures = arm["source_role_contract_failures"]
    failures = viability(
        arm["reports"],
        report["reports"]["legacy"],
        [*arm["frozen_contract_failures"], *role_failures["arm"]],
    )
    requires_expansion = not failures and not role_failures["baseline"]
    if (
        arm.get("diagnostic_failure_reasons") != failures
        or arm.get("fixed_role_contract_blocks_selection") is not bool(role_failures["arm"])
        or arm.get("empty_noise_blocks_selection")
        is not any(failure.endswith(":additional_empty_case_labels") for failure in failures)
        or arm.get("requires_selection_expansion_before_holdout") is not requires_expansion
    ):
        raise ValueError("Frozen source-role diagnostic decision does not match its evidence")
    if role_failures["baseline"]:
        raise ValueError("Selected baseline violates the fixed source-role regression contract")
    if requires_expansion:
        raise ValueError("Source-role ablation qualifies; expand selection before holdout")


def boilerplate_panel(runner: PolicyRunner, policies: Mapping[str, Mapping[str, bool]]) -> Any:
    controls = json.loads((REPO / CONTROLS).read_text())
    panel = {}
    for name, policy in policies.items():
        cases = []
        for note in controls["notes"]:
            explanation = runner.explanation(note["content"], policy, legacy=name == "legacy")
            protected = []
            for label in note["protected_candidates"]:

                class Injected:
                    def extract_keywords(self, text: str, /) -> list[tuple[str, float]]:
                        return [(label, 0.1)]

                injected = runner.explanation(
                    note["content"], policy, legacy=name == "legacy", extractor=Injected()
                )
                statistical = [row for row in injected.candidates if row.provenance == "yake"]
                protected.append(
                    {
                        "label": label,
                        "decisions": [asdict(row) for row in statistical],
                        "eligible_before_ranking": any(
                            occurrence.allowed
                            for row in statistical
                            for occurrence in row.inspected_occurrences
                        ),
                        "statistical_candidate_selected": any(row.selected for row in statistical),
                        "assigned": [tag.key for tag in injected.topics],
                    }
                )
            cases.append(
                {
                    "id": note["id"],
                    "kind": note["kind"],
                    "assigned": [asdict(tag) for tag in explanation.topics],
                    "protected_injected_candidates": protected,
                }
            )
        panel[name] = cases
    return {"diagnostic_only": True, "used_for_selection": False, "policies": panel}


def calibrate(lyt: Path, plan: Mapping[str, Any]) -> dict[str, Any]:
    from scripts import evaluate_topics as evaluation

    if "source_role_ablation" not in plan:
        raise ValueError("Source-role ablation must be preregistered before calibration outputs")
    runner = PolicyRunner()
    policies = {policy_name(policy): policy for policy in all_policies()}
    policies["legacy"] = dict.fromkeys(RULES, True)
    reports: dict[str, dict[str, Any]] = {name: {} for name in policies}
    sources = {}
    contract_results = {}
    for name, policy in policies.items():
        contract_results[name] = frozen_contracts(
            runner, policy, legacy=name == "legacy", functions=plan["frozen_contract_functions"]
        )
    with calibration_sources(lyt) as fixtures:
        for fixture_name, (fixture_path, source_root) in fixtures.items():
            gold = json.loads(fixture_path.read_text())
            empty_ids = {note["id"] for note in gold["notes"] if not note["expected"]}
            contents = {note["id"]: verified_content(note, source_root) for note in gold["notes"]}
            sources[fixture_name] = {
                "fixture_sha256": sha256(fixture_path.read_bytes()),
                "notes": {
                    note["id"]: {
                        "source_path": note.get("source_path"),
                        "source_sha256": sha256(contents[note["id"]].encode()),
                        "prose_sha256": sha256(
                            evaluation.topic_prose(contents[note["id"]]).encode()
                        ),
                    }
                    for note in gold["notes"]
                },
            }
            for name, policy in policies.items():
                runner.summaries = {}

                def extract(content: str) -> Any:
                    return runner.extract(content, policy, legacy=name == "legacy")

                with patch.object(evaluation, "extract_topics", extract):
                    report = evaluation.evaluate_gold(fixture_path, source_root=source_root)
                report["empty_case_predictions"] = {
                    case["id"]: case["predictions"]["yake"]
                    for case in report["cases"]
                    if case["id"] in empty_ids
                }
                report["decision_summary"] = {
                    identifier: runner.summaries.get(sha256(content.encode()), {})
                    for identifier, content in contents.items()
                }
                reports[name][fixture_name] = report
        previous = asdict(runner.selection.DEFAULT_POLICY)
        decision = select_policy(reports, previous, contract_results)
        chosen = decision["selected_policy"]
        explanations = {}
        if decision["viable_policy_found"]:
            for fixture_name, (fixture_path, source_root) in fixtures.items():
                explanations[fixture_name] = {
                    note["id"]: asdict(
                        runner.explanation(verified_content(note, source_root), chosen)
                    )
                    for note in json.loads(fixture_path.read_text())["notes"]
                }
        panel = boilerplate_panel(runner, policies)
        role_ablation = source_role_ablation(plan, chosen, fixtures, runner, reports["legacy"])
    return {
        "format": FORMAT,
        "phase": "calibrate",
        "legacy_comparator": LEGACY_COMPARATOR,
        "receipt": receipt(),
        "previous_production_policy": previous,
        **decision,
        "frozen_contract_failures": contract_results,
        "sources": sources,
        "reports": reports,
        "winner_explanations": explanations,
        "yake_proposals": {
            sha256(prose.encode()): list(proposals)
            for prose, proposals in runner.proposals.proposals.items()
        },
        "boilerplate_panel": panel,
        "source_role_ablation": role_ablation,
        "limitation": "Calibration/constructed contrasts; fresh sources were not opened.",
    }


def load_selection_archive(path: Path) -> tuple[list[dict[str, Any]], dict[str, bytes]]:
    """Use the shared bounded, integrity-checked archive reader without extracting files."""
    from scripts.topic_evidence_archive import load_archive

    return load_archive(path)


def calibration_report_input(path: Path) -> tuple[bytes, bytes, dict[str, Any]]:
    """Retain exact committed envelope and logical report bytes for separate receipts."""
    raw = path.read_bytes()
    logical_raw = raw
    envelope = json.loads(raw)
    if isinstance(envelope, dict) and envelope.get("format") == EVIDENCE_FORMAT:
        entries, files = load_selection_archive(path)
        if len(entries) != 1 or len(files) != 1 or entries[0]["path"] not in files:
            raise ValueError("Calibration selection archive must contain exactly one report")
        logical_raw = files[entries[0]["path"]]
    report = json.loads(logical_raw)
    if not isinstance(report, dict):
        raise ValueError("--selection must contain a calibration report object")
    return raw, logical_raw, report


def frozen_selection(path: Path, current_policy: Mapping[str, bool]) -> dict[str, Any]:
    raw, logical_raw, report = calibration_report_input(path)
    if report.get("format") != FORMAT or report.get("phase") != "calibrate":
        raise ValueError("--selection must be a calibration receipt")
    chosen = validate_policy(report["selected_policy"])
    if chosen != dict(current_policy):
        raise ValueError("Production DEFAULT_POLICY must equal the frozen selected policy")
    if (
        report.get("selection_outcome") != "ranked_eligible_policy"
        or report.get("viable_policy_found") is not True
    ):
        raise ValueError("Holdout requires a ranked eligible local policy; no eligible fallback")
    recomputed = select_policy(
        report["reports"], report["previous_production_policy"], report["frozen_contract_failures"]
    )
    if not recomputed["viable_policy_found"] or chosen != recomputed["selected_policy"]:
        raise ValueError("Recorded selection does not match frozen calibration ranking")
    relative = path.resolve().relative_to(REPO.resolve())
    committed = subprocess.check_output(["git", "show", f"HEAD:{relative.as_posix()}"], cwd=REPO)
    if committed != raw:
        raise ValueError("Calibration selection receipt must be committed unchanged before holdout")
    for relative_path in (PLAN, *CALIBRATION.values()):
        expected = report["receipt"]["file_sha256"].get(str(relative_path))
        if relative_path in CALIBRATION.values():
            fixture_name = next(
                name for name, value in CALIBRATION.items() if value == relative_path
            )
            expected = report["sources"][fixture_name]["fixture_sha256"]
        if sha256((REPO / relative_path).read_bytes()) != expected:
            raise ValueError(f"Frozen calibration plan/fixture changed: {relative_path}")
    validate_source_role_receipt(report, json.loads((REPO / PLAN).read_text()))
    measured = receipt()
    for filename, digest in report["receipt"]["file_sha256"].items():
        if filename == "src/geistfabrik/topic_selection.py":
            continue
        if measured["file_sha256"].get(filename) != digest:
            raise ValueError(f"Measured implementation/dependency input changed: {filename}")
    for field in ("selection_logic_sha256", "grammar_dependency_sha256", "dependency_versions"):
        if measured[field] != report["receipt"][field]:
            raise ValueError(f"Measured implementation/dependency changed: {field}")
    return {
        **report,
        "selection_report_sha256": sha256(raw),
        "logical_calibration_report_sha256": sha256(logical_raw),
    }


def holdout(lyt: Path, selection_path: Path) -> dict[str, Any]:
    from geistfabrik import topic_selection as selection

    calibration = frozen_selection(selection_path, asdict(selection.DEFAULT_POLICY))
    plan = json.loads((REPO / PLAN).read_text())
    fresh = plan["fresh_evaluation"]
    manifest_path = REPO / PLAN.parent / fresh["selection_manifest"]
    gold_path = REPO / PLAN.parent / fresh["annotations"]
    for filename, digest in fresh["frozen_sha256"].items():
        if sha256((REPO / filename).read_bytes()) != digest:
            raise ValueError(f"Fresh annotation/selection changed after calibration: {filename}")
    manifest = json.loads(manifest_path.read_text())
    gold = json.loads(gold_path.read_text())
    contents = verify_fresh_sources(manifest, gold, lyt)
    runner = PolicyRunner()
    chosen = calibration["selected_policy"]
    policies = {
        "selected": chosen,
        "clean-yake": dict.fromkeys(RULES, False),
        "legacy": dict.fromkeys(RULES, True),
    }
    reports = {}
    explanations = {}
    for name, policy in policies.items():
        predictions = {}
        for identifier, content in contents.items():
            explanation = runner.explanation(content, policy, legacy=name == "legacy")
            predictions[identifier] = [tag.key for tag in explanation.topics]
            if name == "selected":
                explanations[identifier] = asdict(explanation)
        reports[name] = score_holdout(gold, predictions, selection.topic_key)
    return {
        "format": FORMAT,
        "phase": "holdout",
        "legacy_comparator": LEGACY_COMPARATOR,
        "receipt": receipt(),
        "selection_report_sha256": calibration["selection_report_sha256"],
        "logical_calibration_report_sha256": calibration["logical_calibration_report_sha256"],
        "selected_policy": chosen,
        "selected_policy_name": policy_name(chosen),
        "selection_performed": False,
        "fresh_selection_sha256": sha256(manifest_path.read_bytes()),
        "fresh_gold_sha256": sha256(gold_path.read_bytes()),
        "sources": {
            identifier: sha256(content.encode()) for identifier, content in contents.items()
        },
        "reports": reports,
        "winner_explanations": explanations,
        "yake_proposals": {
            sha256(prose.encode()): list(proposals)
            for prose, proposals in runner.proposals.proposals.items()
        },
        "annotation_provenance": gold.get("provenance"),
        "limitation": fresh["limits"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("calibrate", "holdout"), required=True)
    parser.add_argument("--lyt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--selection", type=Path)
    args = parser.parse_args(argv)
    if args.phase == "holdout" and args.selection is None:
        parser.error("--phase holdout requires --selection with a committed calibration receipt")
    plan = json.loads((REPO / PLAN).read_text())
    if tuple(plan["factorial_rules"]) != RULES or plan["label_limit"] != 5:
        raise ValueError("Frozen factors or label limit changed")
    validate_checkout(args.lyt)
    result = (
        calibrate(args.lyt, plan)
        if args.phase == "calibrate"
        else holdout(args.lyt, args.selection)
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(json_bytes(result))
    print("\n".join(archive_lines(result)), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
