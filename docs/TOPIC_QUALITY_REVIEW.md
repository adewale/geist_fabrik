# Topic quality review packet

**Status: awaiting human review; no merge recommendation or approval is recorded.**

This is a historical pre-grammar packet. Its prediction hashes and counts below
belong to the stated older revision. Current outputs and source checksums are in
the [grammar comparison reports](../benchmarks/results/topics/quality-repair/probe/index.json)
and [corpus evaluation](TOPIC_CORPUS_EVALUATION.md). The existing response record
remains unrated; it is not approval of the newer extraction policy.

This packet makes the remaining [quality delivery gate](../specs/TOPIC_EVIDENCE_SPEC.md) reviewable. It freezes the existing ten real starter-vault sources and the assigned labels from the verified implementation. It adds no runtime policy and changes neither the calibration oracle nor its thresholds.

Implementation: `32db958961e4a5ddbc9b61b44fd0cdc961df52fb`; fully validated PR revision: `722a546818cdf071b1565eeebed4c0d6f08eb079`. The [pending response record](../benchmarks/reviews/topics/pending.json) binds source and prediction hashes and contains no completed human judgments.

## Scope and decision

- Ten public starter notes: seven substantive notes and three metadata-only/stub cases. The extractor assigned 34 labels; the frequency baseline assigned 35. Every assigned label must be judged.
- These notes concentrate on Obsidian and note-taking. They do not establish representativeness for a broader personal vault. The larger narrative corpus in this repo is fictional and cannot substitute for real-vault evidence.
- This is human adjudication of an existing calibration set, not an untouched holdout. [Existing larger corpora from merged PRs](TOPIC_CORPUS_EVALUATION.md) are now being reused, including a pinned authored LYT Kit mirror. They extend the evidence without claiming fictional notes are real or fabricating human ratings.
- Preserve the frozen thresholds: precision >= 0.50 and recall >= 0.60, with no false topics on empty cases. Do not lower these thresholds or rewrite the existing oracle to obtain a pass.

## Pass 1: read the sources before the predictions

For each source, record its central subjects in your own wording (`expected_groups` in the response record). Use visible note text, including visible link wording; exclude frontmatter, code, embedded content, link destinations, filenames alone and generic structural labels. Empty/stub cases should have no required subjects. Do this before reading Pass 2.

The question is whether a topic would help you retrieve this note. Source occurrence alone does not make an incidental example, navigation label or phrase fragment useful. A useful secondary subject is allowed, and a singleton subject remains valid. Membership says nothing about stance or intent.

### 1. japan-trip-metadata-only

[Original source](../testdata/kepano-obsidian-main/2023%20Japan%20Trip.md) · SHA256 `5ca2c825c82ec4f8b5f906a821a34ff78657f474f44dd1a76d7fc586be041542`

````markdown
---
categories:
  - "[[Trips]]"
start: 2023-09-12
end: 2023-09-30
loc:
  - "[[Kyoto]]"
  - "[[Japan]]"
tags:
  - trips
---
````

Human central subjects: **pending**.

### 2. meeting-emergence

[Original source](../testdata/kepano-obsidian-main/2023-09-12%20Meeting%20with%20Steph.md) · SHA256 `ef32b9eec86e95582b36d22623e2e5732f4dd3beb07dbae059171695724bc435`

````markdown
---
categories:
  - "[[Meetings]]"
type: []
date: 2023-09-14
org:
  - "[[Obsidian]]"
loc:
  - Remote
people:
  - "[[Steph Ango]]"
topics:
  - "[[Emergence]]"
tags:
  - meetings
---
- Discussed the book [[Out of Control]] on the topic of [[Emergence]]
````

Human central subjects: **pending**.

### 3. daily-2023-09-12-stub

[Original source](../testdata/kepano-obsidian-main/2023-09-12.md) · SHA256 `d2b39819b63832bf6300634cfebde2b6e24d97af03fd03e69b1739504bd95b7d`

````markdown
---
tags:
  - daily
---
## Notes

![[Daily.base]]
````

Human central subjects: **pending**.

### 4. daily-2023-09-30-stub

[Original source](../testdata/kepano-obsidian-main/2023-09-30.md) · SHA256 `d2b39819b63832bf6300634cfebde2b6e24d97af03fd03e69b1739504bd95b7d`

````markdown
---
tags:
  - daily
---
## Notes

![[Daily.base]]
````

Human central subjects: **pending**.

### 5. evergreen-notes

[Original source](../testdata/kepano-obsidian-main/Evergreen%20notes%20turn%20ideas%20into%20objects%20that%20you%20can%20manipulate.md) · SHA256 `d7ec083b3c9a66dea05245bbc89febbaf3e187f7a9fe8fb23a2175966dfa4215`

````markdown
---
categories:
  - "[[Posts]]"
  - "[[Clippings]]"
created: 2023-09-14
url: https://stephango.com/evergreen-notes
author:
  - "[[Steph Ango]]"
published: 2022-09-16
topics:
  - "[[Evergreen]]"
tags:
  - 0🌲
  - clippings
status:
  - "[[Published]]"
---
Using [[evergreen]] notes in [[Obsidian]] has been the most impactful change to how I think.

Evergreen notes allow you to think about complex ideas by building them up from smaller composable ideas.

See also: [[Obsidian]]

My evergreen notes have titles that distill each idea in a succinct and memorable way, that I can use in a sentence. For example:

- [[A company is a superorganism]]
- [[All input is error]]
- [[Calmness is a superpower]]
- [[Cross the chasm]]
- [[Everything is a remix]]
- [[Writing is telepathy]]
- [[You have no obligation to your former self]]
- etc

You don’t need to agree with the idea for it to become an evergreen note. Evergreen notes can be very short.

I have an evergreen note called [[Creativity is combinatory uniqueness]] that is built on top of another evergreen note:

> If you believe [[Everything is a remix]], then creativity is defined by the uniqueness and appeal of the combination of elements.

Evergreen notes turn ideas into objects. By turning ideas into objects you can manipulate them, combine them, stack them. You don’t need to hold them all in your head at the same time.
````

Human central subjects: **pending**.

### 6. isolated-thought

[Original source](../testdata/kepano-obsidian-main/Isolated%20thought.md) · SHA256 `c0edc383fcb28ea15872cc92903b3fdfeb9da604de5dcb88e60187678b5c7831`

````markdown
# Isolated thought

This is a standalone note with no links to or from other notes.

It exists in isolation, making it an orphan in the vault's knowledge graph.
````

Human central subjects: **pending**.

### 7. minimal-theme

[Original source](../testdata/kepano-obsidian-main/Minimal%20Theme.md) · SHA256 `16d99bfd0fdf5dd80eaa043e2d4b41a98670abf13445cf7d6830f9057d4f10ad`

````markdown
---
categories:
  - "[[Projects]]"
type:
  - "[[UI]]"
org:
  - "[[Obsidian]]"
year: 2020
tags:
  - projects
url: https://minimal.guide
status:
  - "[[Active]]"
---

A theme for [[Obsidian]] focused on minimalism and usability.

## To-do

- [x] Color schemes
- [x] E-ink mode
- [x] Mobile support

Related: [[Obsidian]]
````

Human central subjects: **pending**.

### 8. obsidian-application

[Original source](../testdata/kepano-obsidian-main/Obsidian.md) · SHA256 `a9889fbf6bae2a8109c065803043c0b523c018823e946cdf57d1eb920443c1bf`

````markdown
---
type:
  - "[[Tools]]"
status:
  - "[[Active]]"
---

A knowledge management and note-taking application.

Related: [[Minimal Theme]], [[Evergreen notes turn ideas into objects that you can manipulate]]
````

Human central subjects: **pending**.

### 9. product-usage-analysis

[Original source](../testdata/kepano-obsidian-main/Product%20usage%20analysis.md) · SHA256 `3b7d468fff01f1ad6f6f3424c97dc0130712c613a6a4c75e82e0c51ca173cbc8`

````markdown
Analysis of cost per use, see [[Buy wisely]]

Using [[Obsidian]] to track product usage patterns.

![[Products.base#Cost per use]]
````

Human central subjects: **pending**.

### 10. vault-template-readme

[Original source](../testdata/kepano-obsidian-main/Readme.md) · SHA256 `c32b01b5b152b7613ac39b57cba6746f415015e1598e95145dfcb938d4788120`

````markdown
My personal [[Obsidian]] vault template. A bottom-up approach to note-taking and organizing things I am interested in. It is in no way dogmatic, just one example of how you can use [[Obsidian]]. Take the parts you like and tailor them to your needs.

See the article [How I use Obsidian](https://stephango.com/vault) on my site for a detailed explanation of this vault structure.

## Get started

1. [Download this vault](https://github.com/kepano/kepano-obsidian/archive/refs/heads/main.zip)
2. Unzip the .zip file to a folder of your choosing
3. Open [[Obsidian]] and create a new vault pointing to that folder
````

Human central subjects: **pending**.

## Pass 2: judge the predictions

For both extractors, mark each label useful or not useful, give a short reason, and identify any central subject it covers. Explicitly adjudicate useful phrase variants; do not let exact spelling alone decide relevance. Unresolved labels remain pending. The model observations below are not human decisions.

| Case | YAKE labels | Frequency baseline labels | Human decisions |
| --- | --- | --- | --- |
| japan-trip-metadata-only | (none) | (none) | Pending |
| meeting-emergence | `emergence`; `out of control`; `book`; `topic` | `book`; `control`; `discussed`; `emergence`; `topic` | Pending |
| daily-2023-09-12-stub | (none) | (none) | Pending |
| daily-2023-09-30-stub | (none) | (none) | Pending |
| evergreen-notes | `cross the chasm`; `evergreen`; `obsidian`; `writing is telepathy`; `notes` | `evergreen`; `notes`; `ideas`; `note`; `creativity` | Pending |
| isolated-thought | `isolated thought`; `standalone note`; `links`; `exists in isolation`; `knowledge graph` | `exists`; `graph`; `isolated`; `isolation`; `knowledge` | Pending |
| minimal-theme | `obsidian`; `usability`; `minimalism`; `theme`; `color schemes` | `obsidian`; `color`; `focused`; `ink`; `minimalism` | Pending |
| obsidian-application | `minimal theme`; `note-taking application`; `knowledge management`; `related`; `evergreen notes` | `application`; `evergreen`; `ideas`; `knowledge`; `management` | Pending |
| product-usage-analysis | `buy wisely`; `obsidian`; `product usage patterns`; `track product usage`; `analysis of cost` | `analysis`; `buy`; `cost`; `obsidian`; `patterns` | Pending |
| vault-template-readme | `obsidian`; `vault template`; `personal`; `folder`; `approach to note-taking` | `obsidian`; `vault`; `folder`; `use`; `approach` | Pending |

## Measurement issues requiring adjudication

The frozen exact-label score is 0.500 precision / 0.857 recall. It is a model-oracle regression metric, not a human estimate that exactly half the labels are useless. Source review identifies both apparent noise and legitimate wording that the oracle may omit:

| Case | Source-grounded question |
| --- | --- |
| Meeting | `book` and `topic` occur in prose but are broad descriptors; the named book and `emergence` carry the subjects. |
| Evergreen notes | `cross the chasm` and `writing is telepathy` appear as example note titles. Are they useful topics of this note, or incidental examples? |
| Isolated thought | `standalone note` directly describes the source, but is absent from the acceptable-label list. `exists in isolation` is a sentence fragment. Judge their retrieval usefulness separately. |
| Minimal Theme | `theme` is broad but literally describes the note. The oracle rejects it; decide whether it is useful at this level of specificity. |
| Obsidian | `note-taking application` directly describes the source but does not exactly equal the expected `note-taking`. `related` is a navigation label. Related-note titles are separately debatable secondary topics. |
| Product usage | `cost per use` is a central subject in visible prose and is missed. `analysis of cost` is only a fragment; the visible link `buy wisely` needs a relevance judgment. |
| Readme | `personal` and `folder` are broad terms. `approach to note-taking` is a supported phrase variant but not in the oracle list. |

No decisions in this table alter the frozen score. No additional stopword list, public-topic threshold, semantic merge, or domain-specific ranking should be introduced merely to improve these ten examples. Human feedback must guide any subsequent change, which must retain the vision constraints and pass regression validation.

## Completing the gate

Fill the response record after reviewing the sources and both prediction sets. For each substantive note, precision counts all useful labels divided by all assigned labels; recall counts central-subject groups covered by useful labels divided by the groups recorded in Pass 1. Macro-average those values over substantive notes, report both extractors, and check empty cases separately. Explicit human mappings can recognize phrase variants without changing the runtime identity policy.

Leave `gate_passed` pending until human judgments, fixed numeric thresholds, empty-case checks and corpus representativeness are all resolved. Do not relabel this model-prepared packet as human-reviewed. A passed review of this narrow corpus alone does not establish general personal-vault quality.

Sources: Steph Ango's checked-in starter vault, copyright 2023 Steph Ango, under its [MIT license](../testdata/kepano-obsidian-main/LICENSE).
