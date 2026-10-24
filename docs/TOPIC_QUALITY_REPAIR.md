# Topic candidate quality repair

The larger vaults exposed incomplete YAKE token windows such as `clinic moved`
and `lena has driven`, generic fragments, and template/publication scaffolding.
They also exposed limits of exact-label evaluation: observed phrases such as
`reduced foot traffic`, `careful refusal`, and `Some Greek Allusions` can be useful
even when only shorter wording appears in the frozen acceptable-label set.
Neither the annotations nor topic identities are changed to obtain higher scores.

## Policy and constraints

YAKE still proposes statistical labels from eligible local prose. A contextual
grammar check rejects clear clause fragments and requires a nominal subject;
this is a fallible candidate heuristic, not an interpretation of the author's
beliefs, emotions or intentions. It uses TextBlob's pinned, packaged English
lexicon and explicit morphology/context/entity rules. Direct Treebank and
data-free Punkt classes require no downloaded NLTK corpus. The actual package
code, rules and tokenizer sources participate in the extraction fingerprint.

The guard preserves these boundaries:

- Authored heading and link priors remain independently eligible. Single-note
  topics, whole short-note labels and nominal outlines remain possible.
- Possessive noun phrases, noun-headed numeric names and postpositive adjectives
  remain eligible. An ambiguous bare verb tag does not alone reject a subject
  such as `Use cases`.
- Tokenizer spans belong to source text. A same-length typographic quote copy is
  used only for grammatical scoring; tags map back to original characters.
  Source evidence and conservative topic identities retain their exact wording.
- Uncertain alignment preserves candidates. A tokenizer alignment failure is
  distinct from an unavailable model; model failures propagate to the existing
  explicit error/incomplete handling. A later eligible occurrence can supply
  evidence when an earlier occurrence is a verb.
- The maximum remains five labels, with no corpus promotion floor, domain
  blacklist, semantic merging, source rewrite, new geist, background process or
  suggestion ranking. Excluded sources never enter grammar processing.

The dependency graph was resolved by uv in an isolated CI copy, then committed.
Normal validation again uses the committed locked graph and frozen execution.
Installed-wheel smoke clears NLTK's resource search path and exercises real
grammar extraction alongside the existing offline model check.

## Rejected shortcuts

The source-bound diagnostic compares every assigned label on all four frozen
fixtures. Removing the link prior reduced narrative precision/recall from
0.448/0.667 to 0.276/0.619 and starter-note scores from 0.500/0.857 to
0.371/0.524. Capping output at four reached narrative precision 0.500 but lost
recall to 0.571. Inserting sentence separators before YAKE scoring improved the
LYT proxy but reduced starter-note scores to 0.414/0.595. None is adopted.

The convenience Pattern parser also failed to forward its packaged contextual
rules. The implementation calls those rules explicitly. Counterexample tests
then exposed possessive modifiers, numeric names and typographic tokenization;
the repair covers their grammatical classes rather than enumerating words.

## Remaining form ambiguity

The unfilled journal form still produces the grammatical phrase
`important action items`. Its Markdown structure alone does not establish that
all its words are disposable prompts. An independent reviewer constructed this
meaningful outline with the same nesting, colon endings and per-item word counts:

```markdown
dates:: 2022-11-21

- Core principles of scientific reasoning
    - Gravity:
    - Entropy:
    - Topology:
- Cyanotypes
- Photograms
- Causal inference
    - Intervention models with confounders:
    - Causal identification under selection:
    - Counterfactual inference methods:
```

A regression preserves its observed rare subjects. Discarding both outlines,
blacklisting journal prompt words, reading excluded templates, or excluding
`Calendar/` would weaken the vision to make one fixture pass. Additional explicit
form evidence or an assessed semantic policy would be needed to close that case.
The empty-case gate remains failed. Human usefulness is also unreviewed; a higher
model proxy score does not close the representative human-review requirement.

## Verification

The [package-verified probe](../benchmarks/results/topics/quality-repair/probe/index.json)
on `f2d58ef7c877f682423543706395122ef522e5b3` reproduces every pre-repair baseline
case exactly. The frozen narrative proxy improves from 0.448/0.667 to 0.571/0.857
precision/recall; LYT improves from 0.482/0.625 to 0.520/0.625. Both original
calibration gates pass, and the LYT empty-form gate still fails. All 178 focused
tests passed; the focused job failed because its formatter changed one file.

Runtime `427afee5a4c7ae5df044441f4f105c288a75c671` completed
[canonical validation](https://github.com/adewale/geist_fabrik/actions/runs/40123416947),
the [platform/package matrix](https://github.com/adewale/geist_fabrik/actions/runs/40123416927)
and [all-six-corpus validation](https://github.com/adewale/geist_fabrik/actions/runs/40123416962).
Results: 178 focused tests, 2,345 unit tests, 86 integration tests, 84.12% branch
coverage and all 158 automatic acceptance criteria. The 83 manual criteria are
not certified. Offline installed packages passed with an empty NLTK resource
search path and real model inference.

The [final corpus reports](../benchmarks/results/topics/corpora/grammar-repair/index.json)
retain all 120 replay snapshots and both static vaults. Inputs match the previous
full run exactly; every evidence span and positive query was checked, all warm
runs extracted zero topics, all four changing corpora matched complete fresh
rebuilds, and sampled stored labels exactly match the quality predictions.
No human ratings or merge recommendation are inferred from these checks.
