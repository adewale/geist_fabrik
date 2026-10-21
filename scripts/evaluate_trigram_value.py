#!/usr/bin/env python3
"""Compare matched lexical question material without inventing historical text.

This is a lexical-only replay of production sync, analysis and word_burst.suggest.
It does not run embeddings, downstream filtering, saved-question history or the
full CLI. A previously frozen protocol is required and bound to every receipt.
"""

import argparse
import hashlib
import json
import platform
import random
import subprocess
import time
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import patch

import geistfabrik
from geistfabrik import GeistFabrikConfig, Session, Vault, VaultContext
from geistfabrik.default_geists.code.word_burst import suggest
from geistfabrik.evidence_identity import interval_evidence_key
from geistfabrik.lexical_candidacy import is_question_lens
from geistfabrik.word_burst_analysis import WordBurstDiagnostics, analyze_word_bursts
from scripts.generate_temporal_corpus import apply_snapshot

MODES = ("dated_cohorts", "observed_additions")
ARMS = (2, 3)
PACKET_SEED = "trigram-value-protocol-v1"


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def _source_inventory(runtime: Path) -> dict[str, str]:
    result = {
        str(path.relative_to(runtime)): _sha256(path.read_bytes())
        for path in sorted((runtime / "src/geistfabrik").rglob("*.py"))
    }
    for filename in (Path(__file__), Path(apply_snapshot.__code__.co_filename)):
        result[f"harness/{filename.name}"] = _sha256(filename.read_bytes())
    return result


def _finding_key(finding: dict) -> str:
    return interval_evidence_key(
        ["word_burst", finding["history_mode"], finding["direction"], finding["term"]],
        finding["start"],
        finding["end"],
    )


def _same_evidence(left: dict, right: dict) -> bool:
    return all(
        left[field] == right[field] for field in ("direction", "start", "end", "support_paths")
    )


def _contains_phrase(longer: str, shorter: str) -> bool:
    words, part = longer.split(), shorter.split()
    return len(part) < len(words) and any(
        words[index : index + len(part)] == part for index in range(len(words) - len(part) + 1)
    )


def compare_contexts(pairs: dict, triples: dict) -> dict:
    """Separate exact common evidence from structurally additional expressions.

    Same-evidence nesting is a redundancy descriptor, not a judgment that the
    longer phrase cannot express a more useful concept.
    """
    common = [f for f in triples["findings"] if len(f["term"].split()) <= 2]
    added = [f for f in triples["findings"] if len(f["term"].split()) == 3]
    nested = [
        finding
        for finding in added
        if any(
            _same_evidence(finding, shorter) and _contains_phrase(finding["term"], shorter["term"])
            for shorter in pairs["findings"]
        )
    ]
    return {
        "common_findings_identical": sorted(map(_canonical, common))
        == sorted(map(_canonical, pairs["findings"])),
        "added_trigram_episodes": len(added),
        "added_trigram_terms": sorted({finding["term"] for finding in added}),
        "same_evidence_nested_episodes": len(nested),
        "other_evidence_episodes": len(added) - len(nested),
        "question_eligible_trigram_episodes": sum(is_question_lens(f["term"]) for f in added),
        "grammatical_boundary_trigram_episodes": sum(
            not is_question_lens(f["term"].split()[0])
            or not is_question_lens(f["term"].split()[-1])
            for f in added
        ),
        "pair_questions": len(pairs["suggestions"]),
        "triple_questions": len(triples["suggestions"]),
        "identical_question_texts": len(
            {s["text"] for s in pairs["suggestions"]} & {s["text"] for s in triples["suggestions"]}
        ),
        "selected_trigram_questions": sum(
            len(s["finding"]["term"].split()) == 3 for s in triples["suggestions"]
        ),
    }


def review_packets(report: dict, ledger: dict) -> tuple[list[dict], list[dict]]:
    """Partially mask arm membership; wording necessarily exposes phrase length.

    Duplicate text within the same date/mode is one review with both arm
    memberships in its separate answer key. Different contexts stay separate.
    """
    grouped: dict[str, dict] = {}
    for row in report["snapshots"]:
        for arm, arm_row in row["arms"].items():
            for mode, result in arm_row["modes"].items():
                for suggestion in result["suggestions"]:
                    identity = _canonical([row["date"], mode, suggestion["text"]])
                    entry = grouped.setdefault(
                        identity,
                        {
                            "date": row["date"],
                            "history_mode": mode,
                            "question": suggestion["text"],
                            "source_documents": suggestion["source_documents"],
                            "memberships": [],
                        },
                    )
                    entry["memberships"].append(
                        {"arm": arm, "evidence_key": suggestion["evidence_key"]}
                    )
    entries = [grouped[identity] for identity in sorted(grouped)]
    random.Random(PACKET_SEED).shuffle(entries)
    packets, answer_key = [], []
    for index, entry in enumerate(entries, 1):
        opaque_id = f"Q{index:03d}"
        packets.append(
            {
                "id": opaque_id,
                **{key: value for key, value in entry.items() if key != "memberships"},
                "frozen_scenario_facts": ledger["scenarios"],
                "assessment": "unreviewed",
            }
        )
        answer_key.append({"id": opaque_id, "memberships": entry["memberships"]})
    return packets, answer_key


def _observe(vault: Vault, observed: datetime) -> dict:
    """Run each mode with a fresh equal-seeded production context."""
    results = {}
    with Session(observed.replace(tzinfo=None), vault.db) as session:
        for mode in MODES:
            vault.config.word_burst.history_mode = mode
            diagnostics = WordBurstDiagnostics()
            started = time.perf_counter()
            findings = analyze_word_bursts(vault, end_day=observed.date(), diagnostics=diagnostics)
            elapsed = time.perf_counter() - started
            context = VaultContext(vault, session)
            suggestions = suggest(context)
            finding_by_key = {_finding_key(f.to_dict()): f for f in findings}
            records = []
            for suggestion in suggestions:
                if suggestion.evidence_key is None:
                    raise RuntimeError("word-burst suggestion has no evidence identity")
                finding = finding_by_key[suggestion.evidence_key]
                sources = []
                for path in finding.support_paths:
                    note = vault.get_note(path)
                    if note is None:
                        raise RuntimeError(f"missing support {path}")
                    sources.append(
                        {
                            "path": path,
                            "title": note.title,
                            "content": note.content,
                            "content_sha256": _sha256(note.content.encode()),
                        }
                    )
                records.append(
                    {
                        **asdict(suggestion),
                        "finding": finding.to_dict(),
                        "source_documents": sources,
                    }
                )
            results[mode] = {
                "analysis_seconds": elapsed,
                "diagnostics": asdict(diagnostics),
                "findings": [finding.to_dict() for finding in findings],
                "suggestions": records,
                "execution_diagnostics": context.execution_diagnostics,
            }
    return results


def evaluate(
    corpus: Path,
    workspace: Path,
    *,
    output: Path,
    protocol: Path,
    ledger: Path,
    limit: int = 24,
    runtime_commit: str | None = None,
) -> dict:
    """Replay source snapshots independently in each arm, retaining failures."""
    if limit < 1:
        raise ValueError("limit must be positive")
    if workspace.resolve().is_relative_to(corpus.resolve()):
        raise ValueError("workspace must be outside the immutable corpus")
    manifest_bytes = (corpus / "manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    ledger_bytes = ledger.read_bytes()
    if _sha256(ledger_bytes) != manifest["ledger_sha256"]:
        raise ValueError("ledger does not match the frozen corpus")
    protocol_bytes = protocol.read_bytes()
    checkout = Path(__file__).resolve().parents[1]
    runtime = Path(geistfabrik.__file__).resolve().parents[2]
    inventory = _source_inventory(runtime)
    if runtime_commit is None:
        runtime_commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=runtime, text=True
        ).strip()
    report: dict[str, Any] = {
        "protocol_sha256": _sha256(protocol_bytes),
        "protocol": protocol_bytes.decode(),
        "manifest_sha256": _sha256(manifest_bytes),
        "ledger_sha256": _sha256(ledger_bytes),
        "runtime_source_commit": runtime_commit,
        "runtime_package": str(Path(geistfabrik.__file__).resolve()),
        "harness_checkout": str(checkout),
        "source_code_sha256": inventory,
        "python": platform.python_version(),
        "execution_path": "production Vault.sync, analyze_word_bursts, word_burst.suggest",
        "embedding_inference": False,
        "downstream_filters": False,
        "persisted_suggestions": False,
        "synthetic": manifest["synthetic"],
        "limit": limit,
        "snapshots": [],
        "errors": [],
    }
    workspace.mkdir(parents=True, exist_ok=False)
    output.parent.mkdir(parents=True, exist_ok=True)
    vaults = []
    try:
        for arm in ARMS:
            config = GeistFabrikConfig()
            config.lexical_analysis.ngram_max = arm
            root = workspace / f"ngram-{arm}"
            apply_snapshot(corpus, root, 0)
            vaults.append(Vault(root, config=config))
            report.setdefault("configurations", {})[str(arm)] = config.to_dict()
        for index, snapshot in enumerate(manifest["snapshots"][:limit]):
            observed = datetime.fromisoformat(snapshot["observed_at"])

            class Clock(datetime):
                @classmethod
                def now(cls, tz=None):
                    return observed.astimezone(tz or UTC)

            row = {"index": index, "date": snapshot["date"], "arms": {}}
            report["snapshots"].append(row)
            for arm, vault in zip(ARMS, vaults, strict=True):
                if index:
                    apply_snapshot(corpus, vault.vault_path, index)
                actual_sources = {
                    str(path.relative_to(vault.vault_path)): _sha256(path.read_bytes())
                    for path in sorted(vault.vault_path.rglob("*.md"))
                }
                if actual_sources != snapshot["files"]:
                    raise RuntimeError("source bytes do not match this historical snapshot")
                with patch("geistfabrik.vault.datetime", Clock):
                    processed = vault.sync()
                row["arms"][str(arm)] = {
                    "processed": processed,
                    "source_snapshot_sha256": _sha256(_canonical(actual_sources).encode()),
                    "lexical_sync": dict(vault.last_lexical_stats),
                    "dictionary_terms": vault.db.execute(
                        "SELECT count(*) FROM lexical_terms"
                    ).fetchone()[0],
                    "modes": _observe(vault, observed),
                }
            row["comparison"] = {
                mode: compare_contexts(
                    row["arms"]["2"]["modes"][mode], row["arms"]["3"]["modes"][mode]
                )
                for mode in MODES
            }
            if not all(item["common_findings_identical"] for item in row["comparison"].values()):
                raise RuntimeError("common 1–2 word findings differ between matched arms")
            output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
            print(
                f"snapshot {index + 1}/{min(limit, len(manifest['snapshots']))}: {row['date']}",
                flush=True,
            )
    except Exception as exc:
        report["errors"].append({"type": type(exc).__name__, "message": str(exc)})
    finally:
        for vault in vaults:
            vault.close()
        report["runtime_source_unchanged"] = inventory == _source_inventory(runtime)
        report["corpus_manifest_unchanged"] = (
            manifest_bytes == (corpus / "manifest.json").read_bytes()
        )
        report["completed"] = (
            not report["errors"]
            and len(report["snapshots"]) == min(limit, len(manifest["snapshots"]))
            and report["runtime_source_unchanged"]
            and report["corpus_manifest_unchanged"]
        )
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    if report["completed"]:
        packets, key = review_packets(report, json.loads(ledger_bytes))
        for suffix, contents in (("review-packets", packets), ("answer-key", key)):
            output.with_name(output.stem + f".{suffix}.json").write_text(
                json.dumps(contents, indent=2, ensure_ascii=False) + "\n"
            )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus", type=Path)
    parser.add_argument("workspace", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=24)
    parser.add_argument(
        "--runtime-commit", help="Explicit source commit for a hash-bound git-archive runtime"
    )
    arguments = parser.parse_args()
    result = evaluate(
        arguments.corpus,
        arguments.workspace,
        output=arguments.output,
        protocol=arguments.protocol,
        ledger=arguments.ledger,
        limit=arguments.limit,
        runtime_commit=arguments.runtime_commit,
    )
    raise SystemExit(0 if result["completed"] else 1)
