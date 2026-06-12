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
            similar = vault.neighbours(note, count=10)

            concrete_neighbours = []
            for other in similar:
                other_content = vault.read(other).lower()
                other_concrete = sum(1 for word in concrete_words if word in other_content)
                if other_concrete >= 2:
                    concrete_neighbours.append(other)

            if concrete_neighbours:
                example = vault.sample(concrete_neighbours, count=1)[0]

                text = (
                    f"[[{note.link_text}]] operates at a high level of abstraction. "
                    f"What if you zoomed in? [[{example.link_text}]] might be a "
                    f"more concrete instance of the same ideas."
                )

                suggestions.append(
                    Suggestion(
                        text=text,
                        notes=[note.link_text, example.link_text],
                        geist_id="scale_shifter",
                    )
                )

        # Highly concrete note - suggest zooming out
        elif concrete_score >= 3 and abstract_score <= 1:
            # Find more abstract similar notes
            similar = vault.neighbours(note, count=10)

            abstract_neighbours = []
            for other in similar:
                other_content = vault.read(other).lower()
                other_abstract = sum(1 for word in abstract_words if word in other_content)
                if other_abstract >= 2:
                    abstract_neighbours.append(other)

            if abstract_neighbours:
                framework = vault.sample(abstract_neighbours, count=1)[0]

                text = (
                    f"[[{note.link_text}]] is very specific and concrete. "
                    f"What if you zoomed out? [[{framework.link_text}]] might provide "
                    f"a broader framework for understanding what makes this case interesting."
                )

                suggestions.append(
                    Suggestion(
                        text=text,
                        notes=[note.link_text, framework.link_text],
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
                        f"[[{abstract.link_text}]] (abstract/theoretical) and "
                        f"[[{concrete.link_text}]] (concrete/specific) are "
                        f"semantically similar but operate at different scales. Could one "
                        f"illuminate the other?"
                    )

                    suggestions.append(
                        Suggestion(
                            text=text,
                            notes=[abstract.link_text, concrete.link_text],
                            geist_id="scale_shifter",
                        )
                    )

    return vault.sample(suggestions, count=2)
