"""Scale Shifter geist - suggests viewing concepts at different levels of abstraction.

Identifies notes and suggests examining the same concept at different scales:
zooming in (more specific/concrete) or zooming out (more abstract/general).
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geistfabrik import Suggestion, VaultContext


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Suggest scale shifts for notes (zoom in/out on abstraction).

    Returns:
        List of suggestions for changing perspective scale
    """
    from geistfabrik import Suggestion

    suggestions = []

    notes = vault.notes_excluding_journal()

    if len(notes) < 20:
        return []

    # Scale indicators
    abstract_words = [
        "theory",
        "principle",
        "concept",
        "framework",
        "paradigm",
        "model",
        "pattern",
        "system",
        "structure",
        "abstract",
        "general",
        "universal",
        "category",
        "class",
    ]

    concrete_words = [
        "example",
        "case",
        "instance",
        "specific",
        "particular",
        "detail",
        "concrete",
        "actual",
        "practical",
        "real",
        "individual",
        "tangible",
        "implementation",
    ]

    for note in vault.sample(notes, min(30, len(notes))):
        content = vault.read(note).lower()

        # Determine if note is abstract or concrete
        abstract_score = sum(1 for word in abstract_words if word in content)
        concrete_score = sum(1 for word in concrete_words if word in content)

        # Highly abstract note - suggest zooming in
        if abstract_score >= 3 and concrete_score <= 1:
            # Find more concrete similar notes
            similar = vault.neighbours(note, k=10)

            concrete_neighbors = []
            for other in similar:
                other_content = vault.read(other).lower()
                other_concrete = sum(1 for word in concrete_words if word in other_content)
                if other_concrete >= 2:
                    concrete_neighbors.append(other)

            if concrete_neighbors:
                example = vault.sample(concrete_neighbors, k=1)[0]

                text = (
                    f"[[{note.obsidian_link}]] operates at a high level of abstraction. "
                    f"What if you zoomed in? [[{example.obsidian_link}]] might be a "
                    f"more concrete instance of the same ideas."
                )

                suggestions.append(
                    Suggestion(
                        text=text,
                        notes=[note.obsidian_link, example.obsidian_link],
                        geist_id="scale_shifter",
                    )
                )

        # Highly concrete note - suggest zooming out
        elif concrete_score >= 3 and abstract_score <= 1:
            # Find more abstract similar notes
            similar = vault.neighbours(note, k=10)

            abstract_neighbors = []
            for other in similar:
                other_content = vault.read(other).lower()
                other_abstract = sum(1 for word in abstract_words if word in other_content)
                if other_abstract >= 2:
                    abstract_neighbors.append(other)

            if abstract_neighbors:
                framework = vault.sample(abstract_neighbors, k=1)[0]

                text = (
                    f"[[{note.obsidian_link}]] is very specific and concrete. "
                    f"What if you zoomed out? [[{framework.obsidian_link}]] might provide "
                    f"a broader framework for understanding what makes this case interesting."
                )

                suggestions.append(
                    Suggestion(
                        text=text,
                        notes=[note.obsidian_link, framework.obsidian_link],
                        geist_id="scale_shifter",
                    )
                )

    # Also suggest cross-scale connections (very abstract + very concrete on same topic)
    abstract_notes = []
    concrete_notes = []

    for note in vault.sample(notes, min(50, len(notes))):
        content = vault.read(note).lower()
        abstract_score = sum(1 for word in abstract_words if word in content)
        concrete_score = sum(1 for word in concrete_words if word in content)

        if abstract_score >= 3 and concrete_score <= 1:
            abstract_notes.append(note)
        elif concrete_score >= 3 and abstract_score <= 1:
            concrete_notes.append(note)

    # Find abstract-concrete pairs with high similarity
    for abstract in vault.sample(abstract_notes, min(10, len(abstract_notes))):
        for concrete in vault.sample(concrete_notes, min(10, len(concrete_notes))):
            if vault.similarity(abstract, concrete) > 0.6:
                if not vault.links_between(abstract, concrete):
                    text = (
                        f"[[{abstract.obsidian_link}]] (abstract/theoretical) and "
                        f"[[{concrete.obsidian_link}]] (concrete/specific) are "
                        f"semantically similar but operate at different scales. Could one "
                        f"illuminate the other?"
                    )

                    suggestions.append(
                        Suggestion(
                            text=text,
                            notes=[abstract.obsidian_link, concrete.obsidian_link],
                            geist_id="scale_shifter",
                        )
                    )

    return vault.sample(suggestions, k=2)
