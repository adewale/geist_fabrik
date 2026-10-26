"""Inspect derived topics without embeddings, geists, or plugin execution."""

import json
import sys
from dataclasses import asdict
from typing import Any

from ..topic_selection import explain_topics
from ..topics import TopicIndex
from ..vault import Vault
from .base import BaseCommand


class TopicsCommand(BaseCommand):
    """User-invoked indexing and source-grounded inspection."""

    def print_verbose(self, message: str) -> None:
        """Keep JSON stdout machine-readable even when config logging is requested."""
        if self.verbose:
            print(message, file=sys.stderr)

    def execute(self) -> int:
        if self.args.explain and not self.args.note:
            raise ValueError("--explain requires --note")
        vault_path = self.get_vault_path(auto_detect=True)
        if vault_path is None:
            return 1
        context = self.setup_command_context(vault_path)
        if context is None:
            return 1
        vault = context.vault
        vault.sync(rebuild_topics=self.args.rebuild)
        index = TopicIndex(vault.db, context.config.filtering.exclude_paths)
        with index.read_snapshot():
            report = self._report(vault, index)
        if self.args.json:
            print(json.dumps(report, ensure_ascii=False, sort_keys=True))
        else:
            self._print_report(report)
        return 0 if report["complete"] else 2

    def _report(self, vault: Vault, index: TopicIndex) -> dict[str, Any]:
        states = index.states()
        eligible = {path: state for path, state in states.items() if state.status != "excluded"}
        incomplete = [
            {"path": path, "status": state.status, "error": state.error}
            for path, state in sorted(eligible.items())
            if state.status != "complete"
        ]
        complete = not incomplete
        report: dict[str, Any] = {
            "complete": complete,
            "eligible_notes": len(eligible),
            "incomplete_notes": incomplete,
        }
        if self.args.explain:
            report["explanation"] = None
        if self.args.note:
            target = self.args.note.strip()
            if target.startswith("[[") and target.endswith("]]"):
                target = target[2:-2].split("|", 1)[0]
            note = vault.get_note(target) or vault.resolve_link_target(target)
            if note is None:
                # A new physical source can fail before a notes row exists.
                path = target if target in states else f"{target}.md"
                state = states.get(path)
                if state is None:
                    raise ValueError(f"Unknown or ambiguous note: {self.args.note}")
                report["note"] = {
                    "path": path,
                    "link": None,
                    "status": state.status,
                    "error": state.error,
                }
                report["topics"] = None
            else:
                state = index.state(note.path)
                report["note"] = {
                    "path": note.path,
                    "link": f"[[{note.link_text}]]",
                    "status": state.status,
                    "error": state.error,
                }
                report["topics"] = (
                    [asdict(tag) for tag in index.tags(note.path)]
                    if state.status == "complete"
                    else None
                )
                if self.args.explain:
                    report["explanation"] = (
                        asdict(explain_topics(note.content)) if state.status == "complete" else None
                    )
        elif self.args.topic:
            report["topic"] = self.args.topic
            if complete:
                paths = index.paths(self.args.topic)
                loaded = vault.get_notes_batch(paths[: self.args.limit])
                report["notes"] = [
                    {"path": path, "link": f"[[{note.link_text}]]"}
                    for path in paths[: self.args.limit]
                    if (note := loaded[path]) is not None
                ]
                report["count"] = len(paths)
            else:
                report["notes"] = None
                report["count"] = None
        else:
            report["topics"] = (
                [{"key": key, "count": count} for key, count in index.catalog()[: self.args.limit]]
                if complete
                else None
            )
        return report

    def _print_report(self, report: dict[str, Any]) -> None:
        print(f"Topic index: {'complete' if report['complete'] else 'incomplete'}")
        print(f"Eligible notes: {report['eligible_notes']}")
        for failure in report["incomplete_notes"]:
            print(f"  {failure['path']}: {failure['status']} ({failure['error'] or 'not indexed'})")
        if "note" in report:
            note = report["note"]
            print(f"{note['link'] or note['path']}: {note['status']}")
            for tag in report["topics"] or []:
                print(f"  {tag['label']} — line {tag['line']}: {tag['text']}")
            if report.get("explanation") is not None:
                for role in report["explanation"]["relevance_exclusions"]:
                    print(f"  relevance: {role['label']} ({role['reason']}, line {role['line']})")
                for candidate in report["explanation"]["candidates"]:
                    disposition = "selected" if candidate["selected"] else "rejected"
                    print(f"  {disposition}: {candidate['label']} ({candidate['reason']})")
        elif "notes" in report:
            if report["notes"] is None:
                print("Membership unavailable while the topic index is incomplete.")
            else:
                print(f"{report['topic']}: {report['count']} source notes")
                for note in report["notes"]:
                    print(f"  {note['link']}")
        elif report["topics"] is not None:
            for topic in report["topics"]:
                print(f"  {topic['key']}: {topic['count']}")
