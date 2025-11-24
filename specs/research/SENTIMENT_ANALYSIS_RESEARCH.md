# Research Summary: Sentiment Analysis and Emotional Modeling for GeistFabrik

*Compiled: November 16, 2025*

This document synthesizes recent academic literature on sentiment analysis and emotional modeling to inform the development of more sophisticated and provocative emotional geists for GeistFabrik. The focus is on frameworks, concepts, and approaches that align with the "muses not therapists" philosophy.

---

## 1. Alternatives to the Valence/Intensity Model

### 1.1 Three Major Theoretical Perspectives

According to current research, there are at least three fundamental views for modeling human emotions:

#### **Categorical/Discrete Emotions Theory**
- Posits that emotions exist as distinct categories: anger, happiness, fear, sadness, etc.
- **Plutchik's Wheel of Emotions** (1980): Eight primary emotions arranged in a wheel structure
  - Primary emotions: joy, sadness, acceptance, disgust, fear, anger, surprise, anticipation
  - **Emotional opposites**: Joy ↔ Sadness, Fear ↔ Anger, Anticipation ↔ Surprise, Disgust ↔ Trust
  - **Intensity levels**: Emotions intensify from outer to inner ring (e.g., annoyance → anger → rage)
  - **Dyads (emotional combinations)**:
    - Primary dyads: Adjacent emotions (joy + trust = love)
    - Secondary dyads: Two emotions apart (anticipation + joy = optimism)
    - Tertiary dyads: Three emotions apart
    - Opposite dyads: Conflicting emotions
  - Source: [Plutchik's Wheel of Emotions - Six Seconds](https://www.6seconds.org/2025/02/06/plutchik-wheel-emotions/)

- **Basic emotions approach**: Panksepp and others conceptualize affect as a set of distinct categories
- Reference: [Categorical vs Dimensional Models](https://benjamins.com/catalog/ceb.7)

#### **Dimensional Models**
- **Russell's Circumplex Model** (1980): All affective states arise from two dimensions
  - **Valence**: Pleasure ↔ Displeasure continuum
  - **Arousal**: Low alertness ↔ High alertness continuum
  - Any emotion can be plotted on this 2D space
  - Sources:
    - [Circumplex Model - Psychology of Human Emotion](https://psu.pb.unizin.org/psych425/chapter/circumplex-models/)
    - Russell, J.A. (1980). *Computational Linguistics*, MIT Press

**Alternative Dimensional Models:**

1. **PANAS Model** (Watson & Tellegen, 1985):
   - Positive Activation ↔ Negative Activation as **independent dimensions** (not opposites!)
   - Groundbreaking insight: You can feel high positive AND high negative affect simultaneously
   - 45-degree rotation from valence/arousal axes
   - Widely validated across cultures and contexts
   - Reference: Watson, D., Clark, L.A., & Tellegen, A. (1988). *Journal of Personality and Social Psychology*, 54(6), 1063-1070

2. **Vector Model** (1992):
   - Assumes underlying arousal dimension
   - Valence determines direction of emotion

3. **PAD Model** (Mehrabian):
   - Three dimensions: Pleasure, Arousal, Dominance

4. **Affect Valuation Theory** (Tsai et al., 2006):
   - Distinguishes **ideal affect** (what you want to feel) vs **actual affect** (what you feel)
   - Provocative for divergence: "What if the emotions you avoid are the ones you need?"

**Critiques of the Circumplex:**
- Recent research shows **ellipse structure** rather than perfect circle
- Arousal dimension systematically deviates from theoretical predictions
- Source: [Ellipse Rather Than Circumplex](https://www.sciencedirect.com/science/article/abs/pii/S0191886921004293)

#### **Appraisal Theories** (Scherer, Roseman, Smith)
- Emotions result from evaluating stimuli against personal goals
- **Scherer's Component Process Model (CPM)**: Sequential checking process:
  1. **Relevance detection**: Novelty, intrinsic pleasantness, goal relevance
  2. **Implications check**: Consequences for goals and needs
  3. **Coping potential**: Can I handle this? Who caused it?
  4. **Normative significance**: Does this align with my values/norms?

- **Core appraisal variables**:
  - Goal relevance (does this matter to me?)
  - Goal congruence/conduciveness (helps or hinders my goals?)
  - Novelty/unexpectedness (how surprising is this?)
  - Certainty (how sure am I about this?)
  - Coping potential (control/power to handle it)
  - Agency (who/what caused this?)

- Sources:
  - [Appraisal Theories State of the Art](https://www.researchgate.net/publication/257495445_Appraisal_Theories_of_Emotion_State_of_the_Art_and_Future_Development)
  - [Component Process Model](https://psu.pb.unizin.org/psych425/chapter/component-process-model-cpm/)

**Provocative potential**: Instead of "what emotion is this?", ask:
- "What goal might this note be serving that you haven't acknowledged?"
- "What if the novelty you're avoiding is exactly what you need?"
- "Which notes are you certain about, and which uncertainty are you suppressing?"

#### **Psychological Constructionism** (Lisa Feldman Barrett)
- **Theory of Constructed Emotion**: Emotions are not reactions but **constructions**
- Emotions are built in the moment from:
  - **Interoception**: Body state predictions (arousal, pleasure)
  - **Concepts**: Culturally learned emotion categories
  - **Social reality**: Collective agreements about what emotions mean

- **Key insight**: "Emotions are constructions of the world, not reactions to it"
- **Implication**: Emotion categories don't have fixed neural essences
- Different cultures literally experience different emotions
- Sources:
  - [Theory of Constructed Emotion - Wikipedia](https://en.wikipedia.org/wiki/Theory_of_constructed_emotion)
  - Barrett, L.F. (2017). [PMC Article](https://pmc.ncbi.nlm.nih.gov/articles/PMC5390700/)

**Provocative for GeistFabrik**: "What if you're labeling this note with the wrong emotion? What if your culture of note-taking has taught you to feel a certain way about this idea?"

### 1.2 Hybrid Approaches
- Growing recognition that categorical and dimensional models are **complementary**, not competing
- People use both categorical perception and dimensional perception to decode emotions
- Reference: [Categorical and Dimensional Perceptions](https://pmc.ncbi.nlm.nih.gov/articles/PMC3379784/)

---

## 2. Emotional Dynamics and Transitions

### 2.1 Affective Instability and Temporal Patterns

**Definition**: "Rapid oscillations of intense affect, with difficulty regulating these oscillations or their behavioral consequences"

**Key Findings from 2024 Research**:

- **Prevalence**: 13.9% in general population, peaks in ages 16-24
- 40-60% prevalence in depression, anxiety, PTSD, OCD
- Source: [Mood Instability: Significance, Definition and Measurement](https://pmc.ncbi.nlm.nih.gov/articles/PMC4589661/)

**Terminology variants** (all describing similar phenomena):
- Mood swings
- Affective instability
- Emotional dysregulation
- Affective lability
- Emotional impulsiveness

### 2.2 Brain State Transitions (2024 Research)

**Novel finding**: Brain-state transitions associated with emotional changes occur **earlier** when the preceding affective state has **similar valence** to the current state.

- Used hidden Markov modeling with music-evoked emotions
- Spatiotemporal patterns along temporoparietal axis reflect emotional transitions
- Source: [Emotions are Dynamic and Contextually Dependent](https://www.eneuro.org/content/12/7/ENEURO.0184-24.2025) (*eNeuro*, 2024)

**Provocative angle**: "What if your vault has emotional momentum? Notes written in similar emotional states might form invisible paths through your thinking."

### 2.3 Temporal Dynamics Measures

**Emotional inertia**: How long emotional states persist
**Affective variability**: How much emotions fluctuate
**Temporal dependency**: How current affect predicts future affect

**2024 Study Finding**: Negative affect **instability** predicts mental health symptoms even when controlling for negative affect **intensity**
- It's not just how negative you feel, but how **unstably** you feel it
- Source: [Negative Affect Instability](https://www.frontiersin.org/journals/psychology/articles/10.3389/fpsyg.2024.1371115/full) (*Frontiers in Psychology*, 2024)

**For GeistFabrik**: Track not just sentiment scores, but:
- Emotional volatility between notes
- Persistence of emotional states across time
- Unexpected emotional jumps

### 2.4 Mathematical Models of Mood Oscillations

**Relaxation oscillator models**: Bipolar disorder dynamics modeled as coupled deterministic dynamics + noise
- Mood described by two independent relaxation oscillators with different variability levels
- Source: [Bipolar Disorder Dynamics](https://royalsocietypublishing.org/doi/10.1098/rsif.2015.0670) (*Journal of The Royal Society Interface*)

**Computational model**: Basal ganglia shows bipolar oscillations between positive and negative mood states
- Source: [Bipolar Oscillations - PMC](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7090114/)

---

## 3. Emotional Complexity

### 3.1 Conceptual Distinctions

**Three forms of emotional complexity:**

1. **Emotional Dialecticism**: Experiencing positive AND negative emotions simultaneously
   - More common in East Asian cultures than Western cultures
   - Cultural difference in tolerance for ambiguity

2. **Emotional Differentiation/Granularity**: Distinguishing fine-grained emotions within same valence
   - Not just "I feel bad" but "I feel disappointed vs. anxious vs. guilty"
   - Associated with better coping and more adaptive behaviors

3. **Mixed Emotions/Ambivalence**: Simultaneous conflicting affective states
   - "I'm excited but terrified"
   - "I love this but hate that I love it"

Source: [Empirical Study on Emotional Complexity](https://www.frontiersin.org/journals/psychology/articles/10.3389/fpsyg.2022.839133/full) (*Frontiers in Psychology*, 2022)

### 3.2 Measurement Approaches

**Emotional Complexity Indicators:**
- **Covariation index (r)**: Correlation between positive and negative emotions
- **Component indices (Cpc, Cunshared)**: Shared vs. unique variance
- **Granularity indices (Ge, Gp, Gn)**: Overall, positive, negative differentiation
- **Variability indices (Vp, Vn)**: Positive and negative fluctuation

**Four mostly independent factors**:
1. Co-occurrence of positive and negative emotions
2. Affective dynamics
3. Positive differentiation
4. Negative differentiation

### 3.3 Emotional Granularity

**Definition**: Ability to make fine distinctions and well-differentiated reports of emotional experience

**Benefits**:
- Better coping styles
- More adaptive behaviors
- Greater emotional awareness

**Contrast with low granularity**: "I feel bad" vs. "I feel disappointed, slightly anxious, and frustrated with myself"

Source: [What Is Complex/Emotional About Emotional Complexity?](https://pmc.ncbi.nlm.nih.gov/articles/PMC6639786/)

### 3.4 Leadership and Cognitive Flexibility

**Finding**: Emotional complexity increases cognitive flexibility
- Leaders experiencing emotional complexity make more adaptive decisions
- Primary function is enhancing cognitive flexibility

Source: [Feeling Mixed, Ambivalent, and in Flux](https://journals.aom.org/doi/10.5465/amr.2014.0355) (*Academy of Management Review*)

**For GeistFabrik**: Complexity is not dysfunction, it's **cognitive richness**
- "What if the notes that confuse you emotionally are your most important ones?"
- "Find the notes where you felt two opposite things at once"

---

## 4. Provocative Framings: Beyond Diagnosis

### 4.1 Emotional Creativity

**Definition**: "The ability to create something new through the influence of emotions evoked from personal experiences or experiences of others"

**Key Findings**:
- Emotional Creativity Inventory (ECI) strongly correlates with openness to experience
- Emotional intensity provides motivational impetus for creativity
- Positive energized moods benefit creative thinking
- BUT: Not all positive moods equally creative

Source: [Uncovering Emotions in Creativity](https://www.psychologytoday.com/us/blog/creativity-the-art-and-science/202303/uncovering-emotions-in-creativity)

**For "Muses Not Therapists"**: Ask not "how do you feel?" but:
- "What emotion could you invent by combining these notes?"
- "What would happen if you felt the opposite of what this note expects?"
- "Which emotion have you never had about your own thinking?"

### 4.2 Narrative Psychology Approaches

**Using narratives to study emotions**:
- Narratives recreate complex, dynamic, temporally-evolving experiences
- Interactive narrative systems (like PACE) predict emotional responses and shape narrative arcs

Source: [Exploration of Emotion Perception in Interactive Digital Narrative](https://pmc.ncbi.nlm.nih.gov/articles/PMC9347217/)

**Emotional Arcs**: Six basic shapes identified through data mining (2016, still influential):
1. **Rags to riches**: Rise
2. **Tragedy/Riches to rags**: Fall
3. **Man in a hole**: Fall then rise
4. **Icarus**: Rise then fall
5. **Cinderella**: Rise-fall-rise
6. **Oedipus**: Fall-rise-fall

Sources:
- [Six Basic Emotional Arcs](https://epjdatascience.springeropen.com/articles/10.1140/epjds/s13688-016-0093-1) (*EPJ Data Science*, 2016)
- [MIT Technology Review](https://www.technologyreview.com/2016/07/06/158961/data-mining-reveals-the-six-basic-emotional-arcs-of-storytelling/)

**2024 Application**: Emotional arc-guided procedural narrative generation for games
- Emotional arcs enhance engagement, narrative coherence, and emotional impact
- Source: [All Stories Are One Story](https://arxiv.org/html/2508.02132v1) (2024)

**For GeistFabrik**: Analyze vault notes for emotional trajectories:
- "Your vault follows a 'man in a hole' pattern - what's the hole?"
- "These three notes form a tragedy arc. What if you wrote the redemption?"
- "Find the Icarus moment where your thinking got too confident"

### 4.3 Affect Labeling: The Power and Peril of Naming

**"Putting feelings into words"**: Implicit emotion regulation strategy

**Positive effects**:
- Prefrontal cortex activation (planning, focus)
- Amygdala quieting (stress reduction)
- Down-regulation of distress independent of timing

**Controversial finding (2023)**: Emotion naming can **impede** regulation
- "Crystallizes" affect, consolidating appraisals
- Limits ability to generate alternative interpretations
- Participants who named emotions before reappraising felt **worse**

Sources:
- [Putting Feelings Into Words](https://journals.sagepub.com/doi/full/10.1177/1754073917742706) (Torre & Lieberman, 2018)
- [Emotion Naming Impedes Regulation](https://pmc.ncbi.nlm.nih.gov/articles/PMC9383041/) (2023)

**Provocative for GeistFabrik**:
- "What if the emotions you've named are the ones trapping you?"
- "Try feeling this note's emotion without naming it"
- "What happens if you use the wrong emotional word for this note on purpose?"

### 4.4 Emotional Contagion in Networks

**Massive-scale Facebook experiment** (689,003 participants):
- Emotional states transfer via contagion **without direct interaction**
- Happens **without awareness** and **without nonverbal cues**
- Source: [Experimental Evidence of Emotional Contagion](https://www.pnas.org/doi/10.1073/pnas.1320040111) (*PNAS*, 2014)

**Key findings**:
- Positive emotions spread differently than negative emotions
- Users more susceptible to adopting **positive** emotions
- But strongly negative stimuli generate strong negative responses
- Emotional communication influenced by group identity, closeness, trust

Source: [Emotional Contagion Research](https://www.frontiersin.org/journals/psychology/articles/10.3389/fpsyg.2022.931835/full) (*Frontiers in Psychology*, 2022)

**For GeistFabrik**: Your vault is a network where emotions spread
- "Which notes are emotional super-spreaders?"
- "What if your angry notes are infecting your calm notes?"
- "Find the note that changed the emotional tone of your thinking"

---

## 5. Text-Based Emotion Detection: State of the Art

### 5.1 Transformer-Based Models (2024-2025)

**Latest Developments**:

**Emotion-Aware RoBERTa (2025)**:
- Integrates Emotion-Specific Attention (ESA) layer
- TF-IDF-based gating mechanism
- **96.77% accuracy**, weighted F1-score of 0.97
- Outperforms baseline RoBERTa, DistilBERT, ALBERT

Source: [Emotion-Aware RoBERTa](https://www.nature.com/articles/s41598-025-99515-6) (*Scientific Reports*, 2025)

**Multilingual Emotion Detection (2025)**:
- XLM-R: 90.3% F1-score
- Multilingual BERT: 84.5% F1-score
- T5: 87.2% F1-score

**Comparative Study (2024)**: Six transformers evaluated
- BERT, RoBERTa, ALBERT, DeBERTa, CodeBERT, GraphCodeBERT
- Improvements: 1.17% to 16.79% in F1 scores

Source: [Emotion Classification in Software Engineering Texts](https://arxiv.org/html/2401.10845v3) (2024)

**Remaining Challenges**:
- Identifying subtle emotional cues
- Handling class imbalances
- Processing noisy/informal input

Reference: [Transformer Models for Emotion Detection - Review](https://link.springer.com/article/10.1007/s10462-021-09958-2)

### 5.2 Lexicon-Based Approaches

**Major Emotion Lexicons**:

1. **NRC Emotion Lexicon** (EmoLex):
   - 8 basic emotions: anger, fear, anticipation, trust, surprise, sadness, joy, disgust
   - 2 sentiments: positive, negative
   - Manual annotations via Amazon Mechanical Turk
   - Source: [NRC Emotion Lexicon](https://saifmohammad.com/WebPages/NRC-Emotion-Lexicon.htm)

2. **LIWC** (Linguistic Inquiry and Word Count):
   - 73 lexicons for text analysis
   - Widely used but domain-specific limitations

3. **Empath**: Constructed manually, primarily English

**Critical Finding**: Using a single lexicon can lead to unreliable conclusions
- **Recommendation**: Use at least two lexicons
- If both agree → reliable evidence
- If they disagree → investigate the differences

Source: [Two is Better Than One](https://pmc.ncbi.nlm.nih.gov/articles/PMC9565755/)

**Known issues**:
- **NRC bias**: "Hell Hath No Fury?" study found gender bias in NRC lexicon
- Lexicons are culturally specific (most in English)
- Domain dependence despite claims of domain-independence

### 5.3 Fine-Grained Emotion Taxonomies

**GoEmotions Dataset** (Google, 2020):
- **58k Reddit comments** with fine-grained emotion labels
- **27 emotion categories**: 12 positive, 11 negative, 4 ambiguous, 1 neutral
- Largest fully-annotated English emotion dataset

**Taxonomy development**:
- Started with 56 emotion categories
- Removed emotions with: low frequency, low interrater agreement, detection difficulty
- Final 27 categories: **94% interrater agreement** (≥2 raters agree on ≥1 emotion)

**Emotions include**: admiration, amusement, anger, annoyance, approval, caring, confusion, curiosity, desire, disappointment, and more

Sources:
- [GoEmotions - Google Research](https://research.google/blog/goemotions-a-dataset-for-fine-grained-emotion-classification/)
- [GoEmotions ACL Paper](https://aclanthology.org/2020.acl-main.372/)

**Contrast with basic six emotions**: Only one positive emotion (joy) vs. 12 positive emotions in GoEmotions

**For GeistFabrik**: Move beyond basic sentiment
- 27 emotions provide nuanced texture
- "Curiosity" is different from "amusement" even though both are positive
- "Annoyance" vs. "anger" vs. "disappointment" - all negative but functionally different

### 5.4 Beyond Polarity: Emotion Mining

**Shift from sentiment analysis to emotion detection**:
- Sentiment: Positive/negative/neutral (coarse)
- Emotion: Specific affective states (fine-grained)

**Why emotion detection matters**:
- "Emotions are finer-grained information extracted from opinions"
- Applications: mental health monitoring, content moderation, conversation understanding

**Computational approaches (three categories)**:
1. **Knowledge-based**: Use lexicons (happy, sad, afraid, bored)
2. **Statistical**: Machine learning (SVM, LSA, bag-of-words, word embeddings, deep learning)
3. **Hybrid**: Combine both approaches

Sources:
- [Current State of Text Sentiment Analysis](https://dl.acm.com/doi/10.1145/3057270) (*ACM Computing Surveys*, 2017)
- [Review on Sentiment Analysis and Emotion Detection](https://link.springer.com/article/10.1007/s13278-021-00776-6) (*Social Network Analysis and Mining*, 2021)

**For GeistFabrik**: Don't just ask "is this note positive or negative?"
- Ask "is this note curious, confused, or contemplative?"
- Track specific emotions, not just valence
- Use emotion trajectories, not just snapshots

---

## 6. Key Concepts for Provocative Geists

### 6.1 Conceptual Frameworks to Explore

**Instead of asking "how do you feel about this note?"**, GeistFabrik geists could ask:

#### From Appraisal Theory:
- "Which notes surprised you with their novelty, but you ignored anyway?"
- "Find three notes that serve the same hidden goal"
- "What if this note's coping strategy is sabotaging another note's success?"
- "Identify notes where you're certain vs. notes where you're avoiding uncertainty"

#### From Psychological Constructionism:
- "What if you're using the wrong cultural script to understand this note?"
- "Reconstruct this note's emotion from scratch - no labels allowed"
- "Which notes are you feeling the way you think you're supposed to, not how you actually do?"

#### From Plutchik's Wheel:
- "Find note pairs that are emotional opposites (joy/sadness, fear/anger)"
- "Which notes are primary emotions and which are dyads (combinations)?"
- "What tertiary emotion would you get by combining these three distant notes?"
- "Find the most intense version of this emotion in your vault (outer → inner ring)"

#### From Dimensional Models:
- "Plot your vault on pleasure/displeasure × arousal/calm axes - what's missing?"
- "Find notes with high arousal but neutral valence (excitement? anxiety?)"
- "What's in your low-arousal positive quadrant? (contentment, peace)"
- "Map your ideal affect vs. actual affect across your vault"

#### From PANAS Independence:
- "Find notes where you felt high positive AND high negative simultaneously"
- "Your most negatively activated notes aren't necessarily low on positive activation"
- "What if the absence of joy doesn't mean the presence of sadness?"

#### From Emotional Complexity:
- "Which notes have the highest emotional granularity? (Most nuanced feelings)"
- "Find your most emotionally dialectic notes (positive AND negative, not mixed)"
- "Where are you emotionally coarse vs. emotionally differentiated?"
- "Notes with low granularity: Go back and add emotional nuance"

#### From Temporal Dynamics:
- "Track emotional inertia: Which emotions persist across multiple notes?"
- "Find your highest affective variability periods"
- "Identify emotional oscillations: Notes that flip-flop between extremes"
- "Where does emotional momentum carry you, even when content changes?"

#### From Emotional Arcs:
- "Your vault's emotional trajectory is 'Icarus' (rise then fall) - why?"
- "Find the 'man in a hole' sequence: Which notes form fall-then-rise?"
- "Complete this Cinderella arc: rise-fall-rise (you're missing the final rise)"
- "What if your saddest note is actually the middle of a redemption arc?"

#### From Affect Labeling:
- "Which notes have you over-labeled emotionally? (Crystallized affect)"
- "Try feeling this note without naming the emotion"
- "What if you deliberately mislabeled this note's emotion? What emerges?"
- "Find notes where naming the feeling trapped you in one interpretation"

#### From Emotional Contagion:
- "Which note is the emotional super-spreader in your vault?"
- "Find notes infected by emotional contagion from other notes"
- "Map emotional networks: How does affect flow through your vault graph?"
- "Quarantine this note - what changes in the emotional ecosystem?"

#### From GoEmotions' 27 Categories:
- "How many of the 27 emotions are represented in your vault?"
- "Find your most 'curious' notes vs. your most 'confused' (both seek information, different valence)"
- "Admiration vs. approval: Which notes inspire awe vs. simple agreement?"
- "Map disappointment, annoyance, and anger - they're different flavors of goal-blocking"

### 6.2 Generative (Not Diagnostic) Approaches

**Therapeutic framing** (AVOID):
- "Your notes show signs of depression"
- "This emotional pattern is unhealthy"
- "You should work on regulating this emotion"

**Generative/Provocative framing** (EMBRACE):
- "What if your most anxious note is your most alive note?"
- "The emotion you're avoiding might be the one you need to write about"
- "Your vault has an emotional blind spot in the low-arousal positive quadrant - what's there?"
- "These notes form an emotional oscillator - what's the frequency of your thinking?"
- "Emotional complexity is cognitive richness, not confusion - lean into it"

### 6.3 Question Templates (Muses, Not Oracles)

**Structure**: "What if...?", "What happens when...?", "Find the note where..."

**Examples**:
- "What if the notes you've labeled as 'sad' are actually 'disappointed' with different goals?"
- "What happens when you read your most 'fearful' note as if it were 'anticipatory'?"
- "Find the note where joy and sadness coexist - that's where the insight lives"
- "Your vault oscillates between anger and fear, never resting in calm - why?"
- "What emotion is completely absent from your vault? Write a note in that emotional space"
- "These three notes form an emotional trajectory: tragedy. Write the redemption arc"
- "Your most emotionally granular note has 7 distinct feelings - can you name them all?"
- "This note is emotionally contagious - it infected 12 other notes. What happened?"

---

## 7. Implementation Recommendations for GeistFabrik

### 7.1 Multiple Emotion Models Simultaneously

**Don't pick one framework** - use multiple lenses:
- Dimensional (valence/arousal) for quick plotting
- Categorical (Plutchik's 8 or GoEmotions' 27) for specificity
- Appraisal-based for goal/relevance analysis
- Temporal dynamics for tracking changes

### 7.2 Local-First Emotion Detection

**For offline operation**:
- Use **lexicon-based approaches** (NRC + LIWC together, as research recommends)
- Consider lightweight transformer if model size permits (DistilBERT-based emotion classifier)
- Sentence-transformers already in use could be extended with emotion-specific fine-tuning

**Trade-offs**:
- Lexicons: Fast, interpretable, but coarse and biased
- Transformers: Accurate, but require model storage and compute
- Hybrid: Best of both - lexicon for real-time, transformer for deeper analysis

### 7.3 Temporal Analysis

**Track across sessions**:
- Emotional volatility over time
- Emotional inertia (persistence)
- Affective oscillations
- Emotional arcs across note sequences

**Use existing temporal embeddings infrastructure** to add emotional dimensions

### 7.4 Provocative Over Prescriptive

**Design principle**: Every emotion insight should generate a **question** or **suggestion**, not a **diagnosis**

**Bad**: "You have high negative affect"
**Good**: "What if your vault's negative affect is actually creative fuel, not a problem?"

**Bad**: "This note is sad"
**Good**: "This note feels sad, but Plutchik says sadness opposes joy - where's the joy hiding?"

---

## 8. Specific Academic References

### Key Papers by Topic

#### Emotion Models:
- Russell, J.A. (1980). "A circumplex model of affect." *Journal of Personality and Social Psychology*.
- Watson, D., Clark, L.A., & Tellegen, A. (1988). "Development and validation of brief measures of positive and negative affect: The PANAS scales." *Journal of Personality and Social Psychology*, 54(6), 1063-1070.
- Plutchik, R. (1980). *Emotion: A Psychoevolutionary Synthesis*. Harper & Row.

#### Appraisal Theory:
- Scherer, K.R. (2019). "The emotion process: Event appraisal and component." *Annual Review of Psychology*. [PDF](https://ppw.kuleuven.be/okp/_pdf/Scherer2019TEPEA.pdf)
- Moors, A., Ellsworth, P.C., Scherer, K.R., & Frijda, N.H. (2013). "Appraisal theories of emotion: State of the art and future development." *Emotion Review*, 5(2), 119-124.

#### Psychological Constructionism:
- Barrett, L.F. (2017). "The theory of constructed emotion: An active inference account of interoception and categorization." *Social Cognitive and Affective Neuroscience*, 12(1), 1-23. [PMC Article](https://pmc.ncbi.nlm.nih.gov/articles/PMC5390700/)

#### Emotional Complexity:
- Ong, D.C., Zaki, J., & Goodman, N.D. (2022). "An empirical study on the evaluation of emotional complexity in daily life." *Frontiers in Psychology*, 13, 839133. [Full text](https://www.frontiersin.org/journals/psychology/articles/10.3389/fpsyg.2022.839133/full)

#### Temporal Dynamics:
- Waugh, C.E., et al. (2024). "Negative affect instability predicts elevated depressive and generalized anxiety disorder symptoms." *Frontiers in Psychology*, 15, 1371115. [Full text](https://www.frontiersin.org/journals/psychology/articles/10.3389/fpsyg.2024.1371115/full)
- Betzel, R.F., et al. (2024). "Emotions in the brain are dynamic and contextually dependent: Using music to measure affective transitions." *eNeuro*, 12(7), ENEURO.0184-24.2025. [Link](https://www.eneuro.org/content/12/7/ENEURO.0184-24.2025)

#### Affect Labeling:
- Torre, J.B., & Lieberman, M.D. (2018). "Putting feelings into words: Affect labeling as implicit emotion regulation." *Emotion Review*, 10(2), 116-124. [Full text](https://journals.sagepub.com/doi/full/10.1177/1754073917742706)

#### Emotional Contagion:
- Kramer, A.D., Guillory, J.E., & Hancock, J.T. (2014). "Experimental evidence of massive-scale emotional contagion through social networks." *PNAS*, 111(24), 8788-8790. [Link](https://www.pnas.org/doi/10.1073/pnas.1320040111)

#### NLP and Emotion Detection:
- Yadollahi, A., Shahraki, A.G., & Zaiane, O.R. (2017). "Current state of text sentiment analysis from opinion to emotion mining." *ACM Computing Surveys*, 50(2), 1-33. [Link](https://dl.acm.org/doi/10.1145/3057270)
- Demszky, D., Movshovitz-Attias, D., Ko, J., et al. (2020). "GoEmotions: A dataset of fine-grained emotions." *ACL 2020*. [ACL Anthology](https://aclanthology.org/2020.acl-main.372/)
- Acheampong, F.A., Wenyu, C., & Nunoo-Mensah, H. (2020). "Text-based emotion detection: Advances, challenges, and opportunities." *Engineering Reports*, 2(7), e12189. [Wiley](https://onlinelibrary.wiley.com/doi/full/10.1002/eng2.12189)
- (2025). "Emotion-Aware RoBERTa enhanced with emotion-specific attention and TF-IDF gating for fine-grained emotion recognition." *Scientific Reports*. [Nature](https://www.nature.com/articles/s41598-025-99515-6)

#### Emotional Arcs:
- Reagan, A.J., et al. (2016). "The emotional arcs of stories are dominated by six basic shapes." *EPJ Data Science*, 5, 31. [Full text](https://epjdatascience.springeropen.com/articles/10.1140/epjds/s13688-016-0093-1)

---

## 9. Summary: Key Takeaways for GeistFabrik

### What to Implement:

1. **Multi-model emotion analysis**: Use dimensional, categorical, and appraisal lenses simultaneously
2. **Temporal tracking**: Emotional arcs, volatility, inertia, oscillations across notes
3. **Fine-grained emotions**: Move beyond positive/negative to 27+ specific emotions (GoEmotions taxonomy)
4. **Complexity metrics**: Granularity, dialecticism, mixed emotions as cognitive richness
5. **Network effects**: Emotional contagion through vault links
6. **Provocative questions**: "What if?" not "You are"

### What to Avoid:

1. **Single-model thinking**: Don't rely only on valence/intensity
2. **Diagnostic language**: No "you have X disorder" or "this is unhealthy"
3. **Prescriptive advice**: No "you should regulate this emotion"
4. **Single lexicon**: Use at least two emotion lexicons for reliability
5. **Static snapshots**: Emotions are dynamic; track changes over time

### Philosophy Alignment:

**"Muses, not therapists"** means:
- **Provocative**, not diagnostic
- **Questions**, not answers
- **Divergent**, not convergent
- **Creative**, not clinical
- **Playful**, not pathologizing

**Emotional analysis in GeistFabrik should**:
- Make you see your notes in a new emotional light
- Ask questions you wouldn't ask yourself
- Highlight emotional patterns you didn't know existed
- Suggest emotional experiments ("What if you felt X instead of Y?")
- Treat emotional complexity as creative opportunity, not dysfunction

---

*End of Research Summary*
