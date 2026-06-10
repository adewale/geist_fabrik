"""Pure-Python linguistic voice analysis for reflective lenses.

Computes observable linguistic signals (verb tense, pronouns, hedging,
sentence structure) from note content. No external lexicons, no models,
no licensing issues — just precompiled regexes and frozensets.

All tense detection is HEURISTIC: it uses suffix patterns and a set of
common irregular past forms rather than proper POS tagging. This trades
depth for reliability and zero dependencies (see
specs/reflective_lenses_spec.md for the rationale and accepted caveats).

Every public function is total: it never raises on arbitrary unicode
input (emoji, CJK, RTL, zero-width joiners, unclosed code fences) and
guards every division by zero.
"""

import re
from typing import Any

# ---------------------------------------------------------------------------
# Precompiled patterns (module level — compiled once)
# ---------------------------------------------------------------------------

# YAML frontmatter at the very start of the document
_FRONTMATTER_RE = re.compile(r"\A---[ \t]*\n.*?\n---[ \t]*\n?", re.DOTALL)

# Fenced code blocks (``` or ~~~). Non-greedy; unclosed fences are left alone.
_FENCED_CODE_RE = re.compile(r"^(```|~~~)[^\n]*\n.*?^\1[^\n]*$", re.DOTALL | re.MULTILINE)

# Inline code spans (single backticks, no newlines)
_INLINE_CODE_RE = re.compile(r"`[^`\n]*`")

# URLs (bare or inside markdown links)
_URL_RE = re.compile(r"(?:https?://|www\.)\S+")

# Lowercase word tokens; keeps internal apostrophes ("won't" is one token)
_WORD_RE = re.compile(r"\w+(?:'\w+)*")

# Sentence boundaries: terminal punctuation followed by whitespace,
# or blank lines (paragraph breaks)
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n{2,}")

# "going to" / "gonna" future markers, counted over lowercased raw text
_GOING_TO_RE = re.compile(r"\bgoing to\b|\bgonna\b")

# ---------------------------------------------------------------------------
# Word sets
# ---------------------------------------------------------------------------

#: Hedge words and phrases (from specs/reflective_lenses_spec.md).
#: Multi-word hedges are matched via a single compiled alternation
#: over lowercased raw text (see _HEDGE_RE below).
HEDGES = frozenset(
    {
        "maybe",
        "perhaps",
        "possibly",
        "probably",
        "apparently",
        "seems",
        "appears",
        "suggests",
        "might",
        "could",
        "may",
        "somewhat",
        "rather",
        "fairly",
        "roughly",
        "approximately",
        "in a way",
        "sort of",
        "kind of",
        "i think",
        "i believe",
        "i guess",
        "i suppose",
        "it seems",
        "arguably",
        "presumably",
    }
)

# Single alternation; longest phrases first so "sort of" wins over "sort"
_HEDGE_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(h) for h in sorted(HEDGES, key=len, reverse=True)) + r")\b"
)

#: Common irregular simple-past forms (heuristic — not exhaustive).
#: Includes the past auxiliaries "was", "were", "had", "did".
IRREGULAR_PAST = frozenset(
    {
        "arose",
        "ate",
        "awoke",
        "bade",
        "beat",
        "became",
        "befell",
        "began",
        "beheld",
        "bent",
        "bet",
        "bit",
        "bled",
        "blew",
        "bore",
        "bought",
        "bound",
        "bred",
        "broke",
        "brought",
        "built",
        "burnt",
        "burst",
        "came",
        "cast",
        "caught",
        "chose",
        "clung",
        "cost",
        "crept",
        "cut",
        "dealt",
        "did",
        "dove",
        "drank",
        "drew",
        "dreamt",
        "drove",
        "dug",
        "fed",
        "fell",
        "felt",
        "fled",
        "flew",
        "flung",
        "forbade",
        "foresaw",
        "forgave",
        "forgot",
        "fought",
        "found",
        "froze",
        "gave",
        "got",
        "grew",
        "ground",
        "had",
        "heard",
        "held",
        "hid",
        "hit",
        "hung",
        "hurt",
        "kept",
        "knelt",
        "knew",
        "laid",
        "lay",
        "leant",
        "leapt",
        "learnt",
        "led",
        "left",
        "lent",
        "let",
        "lit",
        "lost",
        "made",
        "meant",
        "met",
        "mistook",
        "outgrew",
        "overcame",
        "overheard",
        "oversaw",
        "overthrew",
        "paid",
        "partook",
        "put",
        "quit",
        "ran",
        "rang",
        "read",
        "rebuilt",
        "repaid",
        "rethought",
        "rewrote",
        "rid",
        "rode",
        "rose",
        "said",
        "sang",
        "sank",
        "sat",
        "saw",
        "sent",
        "set",
        "sewed",
        "shed",
        "shone",
        "shook",
        "shot",
        "showed",
        "shrank",
        "shut",
        "slept",
        "slew",
        "slid",
        "slung",
        "smelt",
        "sold",
        "sought",
        "sowed",
        "spat",
        "sped",
        "spelt",
        "spent",
        "spilt",
        "split",
        "spoilt",
        "spoke",
        "sprang",
        "spread",
        "spun",
        "stank",
        "stole",
        "stood",
        "strode",
        "strove",
        "struck",
        "stuck",
        "stung",
        "swam",
        "swept",
        "swore",
        "swung",
        "taught",
        "thought",
        "threw",
        "thrust",
        "told",
        "took",
        "tore",
        "trod",
        "undertook",
        "underwent",
        "understood",
        "undid",
        "unwound",
        "upheld",
        "upset",
        "was",
        "went",
        "wept",
        "were",
        "withdrew",
        "withheld",
        "withstood",
        "woke",
        "won",
        "wore",
        "wound",
        "wove",
        "wrote",
        "wrung",
    }
)

#: Future-tense auxiliary tokens ("going to"/"gonna" counted separately)
_FUTURE_TOKENS = frozenset({"will", "shall", "won't"})

#: Present-tense auxiliaries. Third-person -s is too noisy to detect,
#: so the heuristic sticks to auxiliaries plus -ing forms (see below).
_PRESENT_TOKENS = frozenset({"is", "are", "am", "be", "being", "do", "does", "has"})

# Pronoun sets
_FIRST_PERSON_SINGULAR = frozenset({"i", "me", "my", "mine", "myself"})
_FIRST_PERSON_PLURAL = frozenset({"we", "us", "our", "ours", "ourselves"})
_SECOND_PERSON = frozenset({"you", "your", "yours", "yourself", "yourselves"})

# Modal verbs
_MODALS = frozenset({"might", "could", "may", "would", "should"})

#: Exact metadata keys produced by compute_voice_metadata()
VOICE_METADATA_KEYS = frozenset(
    {
        "past_tense_ratio",
        "future_tense_ratio",
        "present_tense_ratio",
        "temporal_orientation",
        "first_person_singular",
        "first_person_plural",
        "second_person",
        "self_focus_ratio",
        "hedging_ratio",
        "question_density",
        "modal_density",
        "mean_sentence_length",
        "sentence_length_variance",
        "lexical_diversity",
    }
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def strip_for_analysis(text: str) -> str:
    """Remove markdown noise before linguistic analysis.

    Strips, in order: YAML frontmatter (only at document start), fenced
    code blocks (``` or ~~~), inline code spans, and URLs. Each removed
    region is replaced with a single space so sentence boundaries survive.

    Unclosed fences/spans are left in place — totality matters more than
    perfect stripping.

    Args:
        text: Raw note content (any unicode)

    Returns:
        Text with code, URLs and frontmatter removed
    """
    text = _FRONTMATTER_RE.sub(" ", text)
    text = _FENCED_CODE_RE.sub(" ", text)
    text = _INLINE_CODE_RE.sub(" ", text)
    text = _URL_RE.sub(" ", text)
    return text


def tokenize(text: str) -> list[str]:
    """Split text into lowercase word tokens.

    Tokens are runs of word characters, optionally joined by internal
    apostrophes ("won't" is a single token). CJK text without whitespace
    yields long tokens — acceptable for a total heuristic function.

    Args:
        text: Text to tokenise

    Returns:
        List of lowercase tokens (possibly empty)
    """
    return _WORD_RE.findall(text.lower())


def split_sentences(text: str) -> list[str]:
    """Split text into sentences.

    Splits on terminal punctuation (. ! ?) followed by whitespace, and
    on blank lines (paragraph breaks). Empty fragments are dropped.

    Args:
        text: Text to split

    Returns:
        List of non-empty sentence strings (possibly empty)
    """
    return [s.strip() for s in _SENTENCE_SPLIT_RE.split(text) if s.strip()]


def count_hedges(text: str) -> int:
    """Count hedge word/phrase occurrences in text.

    Strips code, URLs and frontmatter, lowercases, then counts matches
    of the single compiled hedge alternation (longest phrase wins).

    Args:
        text: Raw note content

    Returns:
        Number of hedge occurrences (>= 0)
    """
    return len(_HEDGE_RE.findall(strip_for_analysis(text).lower()))


def compute_voice_metadata(content: str) -> dict[str, Any]:
    """Compute linguistic voice metadata for note content.

    Performs a single pass over the token stream, deriving all token-level
    features (tense counts, pronouns, modals, lexical diversity) from that
    one stream. Tense detection is HEURISTIC:

    - Past: tokens ending in "ed" (length > 3) plus a set of common
      irregular past forms (including "was", "were", "had", "did")
    - Future: "will"/"shall"/"won't" tokens plus "going to"/"gonna"
      occurrences in the raw text
    - Present: auxiliaries ("is", "are", "am", "be", "being", "do",
      "does", "has") plus tokens ending in "ing" (length > 4);
      third-person -s is too noisy to detect

    Total function: never raises on arbitrary unicode, and every division
    is guarded (empty notes, no verbs, no sentences all yield 0.0 — except
    self_focus_ratio, which defaults to 0.5 when no first-person pronouns
    are present).

    Args:
        content: Raw note content

    Returns:
        Dictionary with exactly these keys:
        past_tense_ratio, future_tense_ratio, present_tense_ratio (floats
        summing to 1.0 when verbs are present, all 0.0 otherwise),
        temporal_orientation ("past" | "future" | "present" | "mixed"),
        first_person_singular, first_person_plural, second_person (per
        100 words), self_focus_ratio, hedging_ratio (hedges per sentence),
        question_density (per 100 words), modal_density (per 100 words),
        mean_sentence_length, sentence_length_variance (in word tokens),
        lexical_diversity (unique/total tokens)
    """
    text = strip_for_analysis(content)
    lowered = text.lower()
    tokens = tokenize(text)
    sentences = split_sentences(text)

    word_count = len(tokens)

    # Single pass over tokens: classify each token once (elif chain
    # prevents double counting, e.g. "being" is auxiliary, not -ing form)
    past = 0
    future = 0
    present = 0
    fps = 0
    fpp = 0
    sp = 0
    modals = 0
    unique_tokens: set[str] = set()

    for token in tokens:
        unique_tokens.add(token)

        if token in IRREGULAR_PAST or (len(token) > 3 and token.endswith("ed")):
            past += 1
        elif token in _FUTURE_TOKENS:
            future += 1
        elif token in _PRESENT_TOKENS or (len(token) > 4 and token.endswith("ing")):
            present += 1

        if token in _FIRST_PERSON_SINGULAR:
            fps += 1
        elif token in _FIRST_PERSON_PLURAL:
            fpp += 1
        elif token in _SECOND_PERSON:
            sp += 1

        if token in _MODALS:
            modals += 1

    # "going to" / "gonna" are future markers not visible token-by-token
    future += len(_GOING_TO_RE.findall(lowered))

    # Tense ratios (all 0.0 when no verbs detected)
    total_verbs = past + future + present
    if total_verbs > 0:
        past_ratio = past / total_verbs
        future_ratio = future / total_verbs
        present_ratio = present / total_verbs
    else:
        past_ratio = future_ratio = present_ratio = 0.0

    if past_ratio > 0.6:
        orientation = "past"
    elif future_ratio > 0.4:
        orientation = "future"
    elif present_ratio > 0.7:
        orientation = "present"
    else:
        orientation = "mixed"

    # Pronoun rates per 100 words (guard empty notes)
    if word_count > 0:
        fps_rate = fps / word_count * 100.0
        fpp_rate = fpp / word_count * 100.0
        sp_rate = sp / word_count * 100.0
    else:
        fps_rate = fpp_rate = sp_rate = 0.0

    self_focus = fps / (fps + fpp) if (fps + fpp) > 0 else 0.5

    # Uncertainty markers
    hedge_count = len(_HEDGE_RE.findall(lowered))
    hedging_ratio = hedge_count / len(sentences) if sentences else 0.0
    question_density = text.count("?") / word_count * 100.0 if word_count > 0 else 0.0
    modal_density = modals / word_count * 100.0 if word_count > 0 else 0.0

    # Structural features (sentence lengths in word tokens)
    sentence_lengths = [len(tokenize(s)) for s in sentences]
    if sentence_lengths:
        mean_length = sum(sentence_lengths) / len(sentence_lengths)
        variance = sum((length - mean_length) ** 2 for length in sentence_lengths) / len(
            sentence_lengths
        )
    else:
        mean_length = 0.0
        variance = 0.0

    lexical_diversity = len(unique_tokens) / word_count if word_count > 0 else 0.0

    return {
        "past_tense_ratio": past_ratio,
        "future_tense_ratio": future_ratio,
        "present_tense_ratio": present_ratio,
        "temporal_orientation": orientation,
        "first_person_singular": fps_rate,
        "first_person_plural": fpp_rate,
        "second_person": sp_rate,
        "self_focus_ratio": self_focus,
        "hedging_ratio": hedging_ratio,
        "question_density": question_density,
        "modal_density": modal_density,
        "mean_sentence_length": float(mean_length),
        "sentence_length_variance": float(variance),
        "lexical_diversity": lexical_diversity,
    }
