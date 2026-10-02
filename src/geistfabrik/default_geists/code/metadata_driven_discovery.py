"""Metadata-Driven Discovery - buried gems.

Pairs two old notes with rich vocabulary that haven't been touched in
months: language and ideas that may be gathering dust.

(Its other patterns moved: long notes with at most one link, grouped in
threes, are link_density_analyser's; stale notes with open tasks, grouped in
twos with "revive or archive?", are task_archaeology's.)
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from geistfabrik import Note, VaultContext

from geistfabrik import Suggestion

# Bound on how many notes the metadata sweeps inspect. vault.metadata() runs
# every enabled inference module per note, so an unbounded full-vault scan can
# be expensive on large vaults or with custom metadata modules. The pattern
# only needs 2 hits, so a sampled candidate set is plenty. The notes it names
# are sampled from all of its matches, so different sessions surface
# different notes rather than the first few in candidate order.
MAX_CANDIDATES = 300

# Vocabulary richness is read from the built-in root_ttr (unique words /
# sqrt(total words)), not raw lexical_diversity: raw TTR falls as a text grows,
# so any stub of distinct words scores ~1.0 and would read as "rich".
# Root TTR cannot exceed sqrt(word_count), so the threshold also implies a
# minimum length (15 needs >= 225 words). On real prose it still rises with
# length (a few hundred words: ~10-15; several thousand: ~25), so a long note
# clears it more easily than a short one.
BURIED_GEM_ROOT_TTR = 15.0


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Pair two buried gems: old notes with rich vocabulary.

    Args:
        vault: VaultContext with access to vault data

    Returns:
        At most one suggestion, naming two notes
    """
    suggestions = []

    # Sample a bounded candidate set rather than a full-vault pass.
    all_notes = vault.notes()
    candidates = vault.sample(all_notes, min(len(all_notes), MAX_CANDIDATES))

    # Old notes with high lexical diversity (buried gems)
    buried_gems = _find_buried_gems(vault, candidates)
    if len(buried_gems) >= 2:
        note_titles = [n.link_text for n in vault.sample(buried_gems, 2)]
        text = (
            "These notes have high lexical diversity but haven't been touched in months:\n"
            + "\n".join(f"- [[{title}]]" for title in note_titles)
            + "\n\nThey might contain rich language and ideas that are gathering dust. "
            + "Worth revisiting?"
        )

        suggestions.append(
            Suggestion(
                text=text,
                notes=note_titles,
                geist_id="metadata_driven_discovery",
            )
        )

    return suggestions


def _root_ttr(metadata: dict[str, Any]) -> float:
    """Root TTR, or 0.0 when missing or non-numeric (e.g. None from a plugin)."""
    value = metadata.get("root_ttr")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0.0
    return float(value)


def _find_buried_gems(vault: "VaultContext", notes: list["Note"]) -> list["Note"]:
    """Find old notes with high lexical diversity."""
    gems = []

    for note in notes:
        metadata = vault.metadata(note)

        root_ttr = _root_ttr(metadata)
        days_since_modified = metadata.get("days_since_modified", 0)

        # High diversity + old = buried gem
        if root_ttr > BURIED_GEM_ROOT_TTR and days_since_modified > 90:
            gems.append(note)

    return gems
