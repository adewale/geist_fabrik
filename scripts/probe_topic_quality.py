"""Diagnose selection policy on frozen sources; never alter production policy or gold.

These are implementation-aware ablations, not fresh validation or owner ratings.
All assigned labels are scored at the existing maximum and fixed thresholds.
"""

import argparse
import hashlib
import json
import subprocess
from dataclasses import asdict
from functools import partial
from importlib.metadata import version
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import yake

from geistfabrik import topics
from scripts import evaluate_topics as evaluation
from scripts.generate_narrative_corpus import generate_narrative_corpus
from scripts.generate_temporal_corpus import apply_snapshot

REPO = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lyt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--grammar", action="store_true")
    args = parser.parse_args()
    observed = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=args.lyt, text=True
    ).strip()
    if observed != "e191473fcb326df78cca8a6c49b29420ab318e46":
        raise AssertionError("LYT source checkout is not the frozen mirror")
    subprocess.run(["git", "diff", "--quiet", "HEAD", "--", "."], cwd=args.lyt, check=True)
    original_labels = topics._explicit_labels
    original_extract = topics.extract_topics
    original_grammar = topics.CandidateGrammar
    candidate_cache = {}

    class NoGrammar:
        def __init__(self, prose, boundaries):
            pass

        def allows(self, label, start, end):
            return True

    class CachedCandidates:
        def extract_keywords(self, text):
            if text not in candidate_cache:
                candidate_cache[text] = yake.KeywordExtractor(**topics._SETTINGS).extract_keywords(
                    text
                )
            return candidate_cache[text]

    extractor = CachedCandidates()

    def without_link_prior(content, prose):
        return (row for row in original_labels(content, prose) if row[3] != "wikilink")

    def selected(
        content,
        *,
        budget=5,
        link_prior=True,
        predicate_penalty=True,
        block_sentences=False,
        grammar=False,
    ):
        boundaries = topics.topic_boundaries(content)

        class BlockCandidates:
            def extract_keywords(self, text):
                if block_sentences:
                    edges = sorted({0, len(text), *boundaries})
                    text = "\n.\n".join(text[a:b] for a, b in zip(edges, edges[1:]))
                return extractor.extract_keywords(text)

        with (
            patch.object(topics, "CandidateGrammar", original_grammar if grammar else NoGrammar),
            patch.object(
                topics, "_explicit_labels", original_labels if link_prior else without_link_prior
            ),
            patch.object(
                topics,
                "_PREDICATE_HINTS",
                topics._PREDICATE_HINTS if predicate_penalty else frozenset(),
            ),
        ):
            return original_extract(
                content, extractor=BlockCandidates() if block_sentences else extractor
            )[:budget]

    policies = {
        "baseline": {},
        "at-most-one": {"budget": 1},
        "at-most-two": {"budget": 2},
        "at-most-three": {"budget": 3},
        "at-most-four": {"budget": 4},
        "without-link-prior": {"link_prior": False},
        "without-predicate-penalty": {"predicate_penalty": False},
        "without-link-prior-at-most-three": {"link_prior": False, "budget": 3},
        "block-sentence-scoring": {"block_sentences": True},
    }
    if args.grammar:
        policies["contextual-grammar"] = {"grammar": True}
    reports = {}
    diagnostics = {}
    with TemporaryDirectory(prefix="topic-quality-probe-") as directory:
        corpus = Path(directory) / "narrative-corpus"
        manifest = generate_narrative_corpus(corpus)
        narrative = Path(directory) / "narrative"
        for record in manifest["snapshots"]:
            apply_snapshot(corpus, narrative, record["index"])
        fixtures = {
            "synthetic": (REPO / "tests/fixtures/topic_gold.json", REPO),
            "public-starter": (REPO / "tests/fixtures/topic_real_gold.json", REPO),
            "narrative": (REPO / "benchmarks/corpora/topic_narrative_proxy_gold.json", narrative),
            "lyt": (REPO / "benchmarks/corpora/topic_lyt_proxy_gold.json", args.lyt),
        }
        for name, (fixture, source_root) in fixtures.items():
            reports[name] = {}
            for policy, options in policies.items():
                with patch.object(evaluation, "extract_topics", partial(selected, **options)):
                    reports[name][policy] = evaluation.evaluate_gold(
                        fixture, source_root=source_root
                    )
            cases = []
            for note in json.loads(fixture.read_text())["notes"]:
                content = evaluation._content(note, source_root)
                prose = topics.topic_prose(content)
                cases.append(
                    {
                        "id": note["id"],
                        "source_sha256": hashlib.sha256(content.encode()).hexdigest(),
                        "assigned": [asdict(tag) for tag in selected(content, grammar=True)],
                        "authored_candidates": list(original_labels(content, prose)),
                        "yake_candidates": extractor.extract_keywords(prose),
                    }
                )
            diagnostics[name] = cases
        result = {
            "measured_git_commit": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=REPO, text=True
            ).strip(),
            "fixture_sha256": {
                name: hashlib.sha256(path.read_bytes()).hexdigest()
                for name, (path, _) in fixtures.items()
            },
            "reports": reports,
            "diagnostics": diagnostics,
            "limitation": (
                "Model-labelled calibration ablations; no human or holdout quality claim."
            ),
            "experimental_grammar_package": version("textblob") if args.grammar else None,
        }
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        print("TOPIC_QUALITY_PROBE_BEGIN", flush=True)
        print(json.dumps(result, ensure_ascii=False), flush=True)
        print("TOPIC_QUALITY_PROBE_END", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
