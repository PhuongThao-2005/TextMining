# Evaluating LLM Reasoning Choices in Legal RAG

> **Status:** This is a forward-looking design. Under the no-rerun constraint,
> use [posthoc_metrics_plan.md](posthoc_metrics_plan.md) as the operative plan;
> it derives every recommendation from the existing saved artifacts only.

## Decision

Evaluate this ablation as an **evidence-use and decision-making** study, not as
another retrieval study. Retrieval is deliberately fixed for every condition, so
retrieval Recall/MRR/NDCG cannot explain a prompt or LLM difference and should
not occupy the main comparison table. The main question is instead:

> Given the same retrieved legal material, does a reasoning-oriented LLM/prompt
> make a more correct, evidence-grounded, appropriately cautious decision than
> a direct-answer prompt?

The primary outcomes should therefore be (1) legal answer correctness, (2)
claim-level grounding and citation entailment, (3) auditable application of the
legal rule to the facts, and (4) appropriate answer/refuse/clarify behavior.
Latency and output cost are co-primary trade-offs, not afterthoughts.

## What the current experiment can and cannot support

The experiment has good controls: its 500 questions, top-10 retrieved context,
retrieval pipeline, temperature, and output limit are fixed. That makes a
within-model Base versus CoT comparison meaningful when both runs completed.

It cannot currently establish that one condition *reasons* better:

- `unanswerable_accuracy` is calculated over all 500 cases in the saved output
  (400 answerable and 100 unanswerable), not solely over the unanswerable set.
  The 0.826/0.840 values in the GPT-4o-mini pair are therefore **answerability
  decision accuracy**, not refusal accuracy. Relabel it now; do not claim a
  1.4-point improvement in refusal behavior.
- Answer exact match, token F1, and ROUGE only assess surface overlap with a
  reference. They cannot distinguish an answer that reaches the right result
  for the right legal reason from an unsupported answer, nor distinguish a
  useful clarification from a generic refusal.
- Citation validity and structural coverage check that a citation marker maps
  to a retrieved identifier. They do not test whether the cited passage entails
  the claim it accompanies. A validity rate of 1.0 is therefore not evidence of
  factual or legal grounding.
- The saved prediction records contain final answers and citation metadata but
  no raw CoT, structured rationale, reasoning-token count, or judge output.
  Reasoning quality cannot be reconstructed reliably from those historical runs.
- Only the GPT-4o-mini Base/CoT pair is complete. Provider-failed or partial
  cells must remain descriptive until all paired cells are rerun.

The existing outputs are still useful for a retrospective appendix: report
paired lexical deltas, response-completion rate, answerability confusion matrix,
structural citation coverage, and latency percentiles for the complete GPT pair.
They cannot be relabeled as claim faithfulness, legal reasoning quality, or
refusal quality.

## What related evaluations measure

| Work | Evaluation setup | Metrics that transfer here | Practical implication |
| --- | --- | --- | --- |
| Legal RAG Bench | Full factorial legal RAG evaluation, with retrieval and reasoning components varied separately. | End-to-end answer quality plus hierarchical error attribution. | Keep retrieval fixed, then condition LLM quality on evidence availability rather than rediscovering retrieval effects.[^1] |
| LegalBench-RAG | Expert-annotated legal questions with a precise minimum supporting segment. | Precision/Recall@k and the effect of context granularity. | Preserve a gold-support/evidence-available label for every question; it enables an LLM evidence-use score.[^2] |
| LegalBench | 162 legal tasks spanning six reasoning types. | Per-skill/task breakdowns rather than one aggregate. | Break results out by legal reasoning type and difficulty; an average can hide a prompt that fails on rule application.[^3] |
| RAGAS | Separates context relevance, faithfulness, and answer relevance; can operate without a reference answer. | Context/answer relevance and answer faithfulness as separate constructs. | Do not substitute lexical overlap for grounding; score answer quality and faithfulness independently.[^4] |
| ARES | Trained evaluators for context relevance, answer faithfulness, and answer relevance, validated against human labels. | Rubric-based judges plus human validation of the evaluator. | Use a fixed, structured judge rubric and calibrate it on a blinded human subset.[^5] |
| RAGChecker | Claim-level diagnostics for retrieved context and generated answer, including supported, unsupported, and missing claims. | Claim recall, claim precision, claim faithfulness, and error localization. | Make the claim—not the whole answer—the unit for grounding evaluation.[^6] |
| ALCE | Long-form QA with citations, evaluating answer correctness, citation quality, and fluency. | Citation entailment/precision and citation completeness. | Separate a well-formed citation from a citation that actually supports its claim; include an oracle-evidence condition.[^7] |
| CoT for citation generation | Tests chain-of-thought prompting in cited generation settings. | Citation-aware answer quality and a direct prompt ablation. | For this ablation, test whether reasoning improves evidence use, not merely whether it changes wording.[^8] |
| Self-RAG | Uses reflection to decide whether evidence is needed and whether it is useful; tests QA, reasoning, factuality, and citation accuracy. | Evidence sufficiency/usefulness judgments and adaptive abstention. | Include evidence-sufficiency and answerability decisions explicitly in the generated record.[^9] |
| RAGTruth | Human-annotated hallucinations in RAG outputs, with word/case-level error analysis. | Unsupported-claim rate and hallucination severity. | Count unsupported legal claims rather than treating a response as simply pass/fail.[^10] |
| UAEval4RAG | Unanswerable questions across six categories; evaluates acceptable response, direct answer, clarification, and rejection. | Acceptable-response rate, answer/clarify/refuse distribution, and category-level results. | Evaluate refusals as decision quality: some cases need a clarification, not a blanket refusal.[^11] |
| R-Tuning | Trains/evaluates correctness awareness and refusal when an answer is unknown. | Known/unknown decision accuracy and false-answer risk. | Report false answer on unanswerables and false refusal on answerables separately.[^12] |
| REVEAL | Tests verification of reasoning-chain steps for relevance, evidence attribution, and logical correctness. | Step/rationale attribution and conclusion consistency. | Score an auditable rationale's evidence and logic; do not claim access to a model's hidden reasoning.[^13] |
| Faithful CoT Reasoning | Shows that conventional CoT can be plausible without being causally faithful to a model's computation. | A caution about interpreting free-form CoT. | Require a short, cited *justification* for audit, and call it a justification—not a faithful internal trace.[^14] |

These studies point to a common pattern: use multiple dimensions, make
unsupported claims visible, and attribute failures to the stage that could have
caused them. No individual aggregate score is adequate for a legal RAG
reasoning claim.

## Recommended experimental design

### 1. Retain a clean prompt/model factorial

For each LLM, run both conditions to completion on exactly the same frozen
question IDs and retrieved context:

| Factor | Levels |
| --- | --- |
| Model | GPT-4o-mini, DeepSeek-V3.1-thinking, GLM-5, Qwen3-8B (or the final selected set) |
| Prompt | Base direct answer; Structured evidence reasoning |
| Evidence regime | Normal retrieved context; oracle/gold support; insufficient or corrupted support |

The normal retrieved-context condition is the primary end-to-end result. The
two diagnostic regimes make the causal claim readable:

- **Oracle support** gives the reasoning ceiling: does the LLM correctly apply
  the law when the required passage is supplied?
- **Insufficient/corrupted support** tests whether it follows evidence rather
  than confidently filling gaps. Construct it by removing the gold support or
  inserting a plausible but temporally invalid/contradictory distractor. Keep
  the final-answer grading key unchanged and flag the regime; do not mix these
  cases into ordinary accuracy.

If this is too expensive for all models, run all conditions on the complete
GPT-4o-mini prompt pair first and use a stratified diagnostic subset (for
example, 25--50 questions per error type) for the other models. Do not compare
an incomplete cell to a completed one as an ablation result.

### 2. Replace free-form CoT with an auditable, concise justification

The reasoning condition should produce a public, evaluable record such as:

```json
{
  "decision": "answer | clarify | refuse",
  "evidence_ids": ["chunk_12", "chunk_31"],
  "rule_or_conditions": "Short statement of the controlling rule, cited.",
  "fact_application": "Which stated facts satisfy or fail each condition.",
  "evidence_sufficiency": "sufficient | insufficient | conflicting",
  "final_answer": "Concise Vietnamese answer with claim-local citations."
}
```

This is not a request to expose private internal reasoning. It is a short,
verifiable legal justification. The Base condition should use the same response
schema but permit empty `rule_or_conditions` and `fact_application`; otherwise
the output format itself becomes a confound. Persist the raw response,
normalized fields, prompt version/hash, retrieved chunk IDs and text, parser
status, token counts, and provider reasoning-token metadata when available.

### 3. Make answerability an annotated decision task

Split the 100 unanswerable questions into explicit labels. Adapt UAEval4RAG to
the legal corpus:

| Question type | Preferred model action |
| --- | --- |
| Out of corpus / evidence absent | Refuse or state that the retrieved material is insufficient |
| Underspecified facts | Ask a targeted clarifying question |
| False legal/factual presupposition | Correct the premise, then answer only if support is sufficient |
| Conflicting or temporally unresolved legal material | Explain the conflict/uncertainty; do not select a rule without support |
| Nonsensical request | Briefly decline and request a meaningful restatement |
| Answerable with supplied support | Answer rather than refuse |

This turns “unanswerable” from a binary abstention target into a useful
decision-policy evaluation.

## Final metric set

Report all metrics as percentages with denominator, 95% paired-bootstrap
confidence interval, and Base-to-Structured delta. Score failed generations as
failed rather than silently excluding them; also show a valid-response-only
view as a sensitivity analysis.

### A. Primary answer and evidence-use outcomes

| Metric | Definition | Why it belongs in the main table |
| --- | --- | --- |
| **Legal answer correctness** | Blinded 0/1/2 rubric: wrong or materially misleading / partly correct / legally correct and responsive. Report normalized mean. | Evaluates the actual user-facing outcome beyond lexical overlap. |
| **Reference-claim coverage** | Fraction of annotated reference claims correctly present in the answer. | Finds incomplete answers that can still sound fluent. |
| **Answer-claim faithfulness** | Supported factual/legal answer claims divided by all verifiable answer claims. | Direct measure of hallucination/grounding. |
| **Citation entailment precision** | Answer claims whose adjacent cited chunk entails/supports them divided by claims with a citation. | Replaces structural citation validity as the quality claim. |
| **Citation completeness** | Supported answer claims that have an adequate local citation divided by all claims requiring support. | Penalizes a correct answer with only decorative citations. |
| **Evidence-use success** | `legal correctness AND answer-claim faithfulness`, calculated only where gold support is present in the supplied context. | The central LLM reasoning measure: it controls for whether evidence was available to use. |
| **Oracle evidence-use success** | The same metric under oracle support. | Separates a reasoning/application limitation from retrieval/context limitations. |

Use semantic/entailment annotation rather than string matching for the last
four metrics. A judge receives only the question, the claim, cited passage(s),
and rubric—not the system/model name or its condition.

### B. Auditable justification outcomes

Score the structured justification only when it is present. It augments rather
than replaces final-answer assessment.

| Metric | Definition |
| --- | --- |
| **Rationale evidence-attribution precision** | Proportion of factual/rule statements in `rule_or_conditions` and `fact_application` that are supported by their cited supplied evidence. |
| **Rule/condition application score** | 0/1/2: does it identify the controlling rule/conditions and correctly map material facts to them? |
| **Conclusion consistency** | Binary: does the stated conclusion follow from the justification and stated evidence? |
| **Sufficiency calibration** | Accuracy of `sufficient/insufficient/conflicting` against the annotated evidence state; show a confusion matrix. |

These are evaluations of the **observable justification**, not claims that
free-form CoT reveals the model's internal causal computation.[^13][^14]

### C. Refusal and clarification outcomes

Never collapse these into one “unanswerable accuracy” value.

| Metric | Denominator | Desired behavior |
| --- | --- | --- |
| **Answerable answer rate** | Answerable questions | Correctly attempts an answer rather than refusing. |
| **False-refusal rate** | Answerable questions | Lower is better; refusal/clarification without a valid reason. |
| **Unanswerable acceptable-response rate** | Unanswerable questions | Correct response type and helpful explanation. |
| **False-answer rate** | Unanswerable questions | Lower is better; provides a definitive unsupported legal answer. |
| **Clarification appropriateness** | Underspecified subset | Targeted clarification rather than answer/refuse. |
| **Refusal grounding rate** | Refuse/clarify outputs | States the missing, conflicting, or out-of-corpus evidence accurately. |
| **Decision confusion matrix** | All questions | Gold preferred action versus `answer/clarify/refuse`. |

Report the category breakdown beside the aggregate. A model that refuses every
unanswerable question can look good in a binary metric while mishandling cases
where a focused clarification is the right legal interaction.[^11]

### D. Reliability and efficiency outcomes

| Metric | Definition |
| --- | --- |
| **Completion rate** | Valid parsed responses / scheduled cases, with provider/parser failures separately listed. |
| **Generation latency p50/p95** | Time spent producing the model response. |
| **Total latency p50/p95** | End-to-end time, reported separately from generation. |
| **Output and justification tokens** | Median and p95; reasoning tokens separately when the provider exposes them. |
| **Cost per valid response** | Token/accounting cost divided by valid parsed response count. |

Do not use mean latency alone: the saved latency artifacts already contain
percentiles, and long-tail latency is a meaningful cost of a reasoning prompt.

## Annotation and judging protocol

1. **Build a case key before running.** For each question, store answerability
   category, preferred action, atomic reference claims, material supporting
   chunk IDs, and legal reasoning type. Have a legal-domain annotator review
   ambiguous cases.
2. **Use claim-level evaluation.** Split each answer into atomic legal/factual
   claims. Judge support against the *provided* context, then judge correctness
   against the reference answer/gold law. This distinguishes an unsupported
   truth from evidence-grounded behavior.
3. **Use blinded structured judges.** A fixed rubric should return JSON with
   each claim's correctness, support, citation entailment, and rationale
   application score plus a short evidence pointer. Randomize system labels and
   order. Keep judge model/version, prompt hash, and raw decision.
4. **Validate the judge with people.** Independently double-annotate a
   stratified blinded sample of at least 150 response cases (answerable,
   unanswerable categories, apparent successes, and apparent failures).
   Report inter-annotator agreement and judge--human agreement; revise the
   rubric before scoring the full set. This follows the calibration principle
   used by ARES rather than treating an LLM judge as ground truth.[^5]
5. **Use paired inference.** Compare prompts per question within model using a
   paired bootstrap confidence interval for every delta (and McNemar's test for
   paired binary outcomes). State the exact paired denominator and do not pool
   models into one prompt effect without a planned model-level analysis.

## Reporting layout

Make the main table intentionally small. It should answer whether structured
reasoning improves outcomes that matter.

| Condition | Complete / scheduled | Legal correctness | Claim faithfulness | Citation entailment | Evidence-use success | Unanswerable acceptable response | Gen p50 / p95 | Total p50 / p95 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Model A, Base |  |  |  |  |  |  |  |  |
| Model A, Structured reasoning |  |  |  |  |  |  |  |  |
| Delta, paired |  |  |  |  |  |  |  |  |

Add three diagnostic displays:

1. **Evidence attribution funnel:** gold support in context -> correct
   sufficiency decision -> faithful answer -> legally correct answer. This
   makes it clear where a reasoning condition helps or harms.
2. **Decision-policy matrix:** preferred action versus answer/clarify/refuse,
   with rows for each unanswerable category and the answerable set.
3. **Error taxonomy:** retrieval unavailable, evidence ignored, wrong rule,
   wrong fact application, unsupported claim, citation mismatch, inappropriate
   refusal, and generation failure. Retrieval-unavailable should remain a
   context-quality label, not be counted as an LLM reasoning error.

Place EM, token F1, ROUGE-L, retrieval Recall@k/MRR/NDCG, and structural
citation-format validity in an appendix. They remain useful diagnostics and
allow continuity with earlier runs, but they should not headline a reasoning
ablation.

## Minimum viable next run

1. Correct the metric name in the report to **answerability decision accuracy**
   and publish the answerable/unanswerable confusion matrix for the existing
   GPT-4o-mini pair.
2. Add the response schema and persistence fields; version the prompt and
   parser. Do not attempt to infer missing historical CoT.
3. Annotate all 100 unanswerable cases with a preferred action and stratify a
   150+-case human-evaluation set across the normal and diagnostic regimes.
4. Rerun the complete Base/Structured pair for each chosen model, including
   completion/failure statistics.
5. Score claim faithfulness, citation entailment, legal rule application, and
   refusal/clarification quality before drawing a conclusion about CoT.

This sequence produces a defensible conclusion even if the lexical scores stay
flat: a reasoning prompt can be shown to improve evidence use and calibrated
caution, or it can be shown to add cost without those benefits.

## Sources

[^1]: Butler, J. and Butler, A. (2026). *Legal RAG Bench: Evaluating End-to-End Legal Retrieval-Augmented Generation Systems.* [arXiv:2603.01710](https://arxiv.org/abs/2603.01710).
[^2]: Pipitone, N. and Houir Alami, G. (2024). *LegalBench-RAG: A Benchmark for Retrieval-Augmented Generation in the Legal Domain.* [arXiv:2408.10343](https://arxiv.org/abs/2408.10343).
[^3]: Guha, N. et al. (2023). *LegalBench: A Collaboratively Built Benchmark for Measuring Legal Reasoning in Large Language Models.* [arXiv:2308.11462](https://arxiv.org/abs/2308.11462).
[^4]: Es, S. et al. (2023). *RAGAS: Automated Evaluation of Retrieval Augmented Generation.* [arXiv:2309.15217](https://arxiv.org/abs/2309.15217).
[^5]: Saad-Falcon, J. et al. (2024). *ARES: An Automated Evaluation Framework for Retrieval-Augmented Generation Systems.* [arXiv:2311.09476](https://arxiv.org/abs/2311.09476).
[^6]: Ru, D. et al. (2024). *RAGChecker: A Fine-grained Framework for Diagnosing Retrieval-Augmented Generation.* [arXiv:2408.08067](https://arxiv.org/abs/2408.08067).
[^7]: Gao, T. et al. (2023). *Enabling Large Language Models to Generate Text with Citations.* [arXiv:2305.14627](https://arxiv.org/abs/2305.14627).
[^8]: Ji, J. et al. (2024). *Chain-of-Thought Improves Text Generation with Citations in Large Language Models.* [AAAI](https://ojs.aaai.org/index.php/AAAI/article/view/29794).
[^9]: Asai, A. et al. (2024). *Self-RAG: Learning to Retrieve, Generate, and Critique through Self-Reflection.* [arXiv:2310.11511](https://arxiv.org/abs/2310.11511).
[^10]: Niu, C. et al. (2024). *RAGTruth: A Hallucination Corpus for Developing Trustworthy Retrieval-Augmented Language Models.* [arXiv:2401.00396](https://arxiv.org/abs/2401.00396).
[^11]: Peng, B. et al. (2025). *UAEval4RAG: Evaluating Unanswerable Questions in Retrieval-Augmented Generation.* [ACL Anthology](https://aclanthology.org/2025.acl-long.415/).
[^12]: Zhang, R. et al. (2024). *R-Tuning: Instructing Large Language Models to Say 'I Don't Know'.* [ACL Anthology](https://aclanthology.org/2024.naacl-long.394/).
[^13]: Agarwal, R. et al. (2024). *A Chain-of-Thought Is as Strong as Its Weakest Link: A Benchmark for Verifiers of Reasoning Chains.* [Google Research](https://research.google/pubs/a-chain-of-thought-is-as-strong-as-its-weakest-link-a-benchmark-for-verifiers-of-reasoning-chains/).
[^14]: Lyu, Q. et al. (2023). *Faithful Chain-of-Thought Reasoning.* [arXiv:2301.13379](https://arxiv.org/abs/2301.13379).
