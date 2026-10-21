"""Bounded presentation policy for lexical questions, separate from exact counts."""

import unicodedata

# The existing Pattern Finder boundary vocabulary, shared without changing its
# phrase extraction policy. These are grammatical words, rather than a general
# IR stop list: words such as "system", "interest" and "fire" can be useful lenses.
ENGLISH_FUNCTION_WORDS = frozenset(
    """
    a an the and or but nor so yet for of to in on at by with from into onto
    over under about as than then that this these those there here it its is
    are was were be been being am do does did done have has had having i me
    my we our us you your he she they them their his her him not no if when
    while which who whom whose what where why how all any each every some
    such can could will would shall should may might must also just only very
    more most other another
    """.split()
)

# Additional closed-class words and contractions for questions. Keep these out
# of the older phrase-boundary policy, whose behavior is intentionally unchanged.
_QUESTION_FUNCTION_WORDS = ENGLISH_FUNCTION_WORDS | frozenset(
    """
    above across after against along although among around because before behind
    below beneath beside between beyond both despite down during either except
    hers herself himself itself neither off ours ourselves out per since theirs
    themselves though through throughout till toward towards unless until up upon
    versus via whether within without yours yourself yourselves
    aren't can't couldn't didn't doesn't don't hadn't hasn't haven't he'd he'll
    he's here's i'd i'll i'm i've isn't it'd it'll it's let's mightn't mustn't
    shan't she'd she'll she's shouldn't that's there's they'd they'll they're
    they've wasn't we'd we'll we're we've weren't what's where's who's won't
    wouldn't you'd you'll you're you've
    """.split()
)


def _is_word(token: str) -> bool:
    """Accept the lexical extractor's letters, marks and internal apostrophes."""
    if not token or not token[0].isalpha():
        return False
    return all(
        character.isalpha()
        or unicodedata.category(character).startswith("M")
        or (character == "'" and i + 1 < len(token) and token[i + 1].isalpha())
        for i, character in enumerate(token)
    )


def is_question_lens(term: str) -> bool:
    """Whether a 1–3-word expression has content for a lexical invitation.

    This English function-word policy is applied only after statistical analysis;
    it neither removes dictionary entries nor changes their exact counts, model
    thresholds or episode evidence. Unknown-language words remain eligible: this
    small policy cannot assess their grammar. Eligibility is necessary, not a
    claim that a word will produce an insightful question.

    Normalization follows the extractor's NFKC/casefold convention. Complete
    tokens matter: "of" is grammatical, but "offer" is a possible lens. Sentence
    punctuation is rejected rather than reinterpreted as a new phrase.
    """
    if not term or len(term) > 100:
        return False
    normalized = unicodedata.normalize("NFKC", term).casefold().replace("\u2019", "'")
    normalized = unicodedata.normalize("NFKC", normalized)
    if len(normalized) > 100 or any(
        character in normalized for character in "\r\n\v\f\x1c\x1d\x1e\x85\u2028\u2029"
    ):
        return False
    words = normalized.split()
    return (
        1 <= len(words) <= 3
        and all(_is_word(word) for word in words)
        and any(word not in _QUESTION_FUNCTION_WORDS for word in words)
    )
