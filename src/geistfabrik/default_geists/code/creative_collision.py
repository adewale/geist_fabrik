"""Creative collision geist - suggests unexpected combinations of notes.

Finds unlinked, only loosely related notes (similarity between
SimilarityLevel.NOISE and SimilarityLevel.WEAK) and suggests combining them
for creative insights.

Absorbed two retired geists: note_combinations (its neutral pairing
templates; the YAML now lives in examples/geists/tracery/ as the note_pairs
+ save-action demo) and temporal_mirror (cross-era juxtaposition, now told
with the notes' real creation dates instead of a "period 7" label, and only
when the pair really was created years apart).
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geistfabrik import Suggestion, VaultContext
    from geistfabrik.models import Note

# A pair created at least this many years apart is framed across eras.
CROSS_ERA_YEARS = 2
_DAYS_PER_YEAR = 365

# Neutral pairing templates (from note_combinations). Each states only what
# was checked: the two notes are unlinked and only loosely related.
TEMPLATES = (
    "What if you combined ideas from [[{a}]] and [[{b}]]? They're unlinked and only "
    "loosely related, which might spark something unexpected.",
    "Consider connecting [[{a}]] and [[{b}]]. They're unlinked and only loosely "
    "related; the contrast could clarify your thinking.",
    "[[{a}]] and [[{b}]] are unlinked and only loosely related. Could their "
    "intersection be fertile ground?",
)
CROSS_ERA_TEMPLATE = (
    "[[{a}]] was created in {a_date} and [[{b}]] in {b_date}, {years} years later. "
    "They're unlinked and only loosely related. What would each era make of the other?"
)


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Suggest creative collisions between unrelated notes.

    Draws 10 random pairs, keeps the unlinked ones inside the loosely-related
    similarity window, samples up to 3 and words each one: a pair created at
    least CROSS_ERA_YEARS apart gets CROSS_ERA_TEMPLATE (older note first,
    real month and year), any other pair a sampled neutral template.

    Returns:
        List of suggestions for creative note combinations
    """
    from geistfabrik.similarity_analysis import SimilarityLevel

    pairs: list[tuple[Note, Note]] = []
    # Random draws can repeat a pair; suggest each pair at most once
    seen_pairs: set[frozenset[str]] = set()

    # Get random pairs of notes
    notes = vault.notes()

    if len(notes) < 2:
        return []

    # Collect candidate pairs
    for _ in range(10):
        pair = vault.sample(notes, count=2)
        if len(pair) != 2:
            continue

        note_a, note_b = pair
        pair_key = frozenset((note_a.path, note_b.path))
        if pair_key in seen_pairs:
            continue
        seen_pairs.add(pair_key)

        # Check if they're unlinked and dissimilar
        if vault.links_between(note_a, note_b):
            continue

        # Compute similarity using individual call to benefit from cache
        similarity = vault.similarity(note_a, note_b)

        # Loosely related: distant, but not completely unrelated. (Up to
        # MODERATE admitted most random pairs in a vault: ~70% on a real one.)
        if SimilarityLevel.NOISE < similarity < SimilarityLevel.WEAK:
            pairs.append((note_a, note_b))

    return [_collide(vault, a, b) for a, b in vault.sample(pairs, count=3)]


def _collide(vault: "VaultContext", note_a: "Note", note_b: "Note") -> "Suggestion":
    """Word one collision, across eras when the notes were created years apart."""
    from geistfabrik import Suggestion

    older, newer = sorted((note_a, note_b), key=lambda n: (n.created, n.path))
    years = (newer.created - older.created).days // _DAYS_PER_YEAR
    if years >= CROSS_ERA_YEARS:
        text = CROSS_ERA_TEMPLATE.format(
            a=older.link_text,
            b=newer.link_text,
            a_date=f"{older.created:%B %Y}",
            b_date=f"{newer.created:%B %Y}",
            years=years,
        )
        named = [older.link_text, newer.link_text]
    else:
        template = vault.sample(TEMPLATES, count=1)[0]
        text = template.format(a=note_a.link_text, b=note_b.link_text)
        named = [note_a.link_text, note_b.link_text]

    return Suggestion(text=text, notes=named, geist_id="creative_collision")
