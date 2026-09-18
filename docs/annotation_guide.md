# Annotation guide: claim support and citation correctness

**Draft for the pilot.** Reconcile it with the second rater after the pilot, then freeze it for the
main pass. Version 0.1, 17 September 2026.

## What you are judging, and what you are not

You are judging whether the instructional text the system produced is **supported by the teaching
corpus**, and whether the **citations it attached point at something that supports the claim**.

You are not judging whether the text is good teaching, well written, well chosen for the learner, or
whether you personally know the claim to be true. A claim you know is true from your own Python
knowledge is still `unsupported` if the corpus does not carry it.

## The units

Responses were split into claims once, automatically, by a fixed rule, so that both raters label
exactly the same units. Do not re-split, merge or skip a claim. If a unit is unjudgeable as given,
label it `not_applicable` and say why in the note column.

Each claim comes with the full response it was taken from, so you can read it in context, and, where
the condition retrieved anything, the passages that response was given.

## The reference: the module corpus

Support is judged against **the whole indexed corpus**, not against the passages a particular
response happened to retrieve. This is what makes the conditions comparable: one of them retrieves
nothing at all, and judging it against its own (empty) context would make its claims unjudgeable.

Search the corpus rather than reading it end to end:

```bash
.venv/bin/python -m src.experiment.corpus search "list comprehension syntax"
```

The corpus is 533 passages from 12 documents: the Python 3.11 tutorial chapters and seven Wikipedia
articles. `data/corpus/python_v1/manifest.json` lists them.

## Dimension 1: claim support (every claim)

| Label | Use when |
|---|---|
| `supported` | The claim follows from at least one corpus passage. A reasonable person reading that passage would accept the claim as stated. |
| `partial` | The corpus bears on the claim but the claim asserts more than the corpus warrants: a stronger generalisation, an extra condition, a specific number the corpus does not give. |
| `unsupported` | Nothing in the corpus bears on the claim. This includes claims that are true but absent from the corpus. |
| `contradicted` | A corpus passage states something incompatible with the claim. |
| `not_applicable` | The claim is definitional or trivially general ("Python is a programming language"), is pure instruction to the learner ("try this yourself"), or is not a factual claim at all. Excluded from the denominator. |

Worked examples:

- "A function definition introduces the function name in the current symbol table." The tutorial says
  exactly this, so `supported`.
- "List comprehensions are always faster than the equivalent for loop." The tutorial describes
  comprehensions as concise; it makes no general speed claim, so `partial`.
- "Python 3.12 added the `type` statement for generic aliases." True, but nothing in this corpus
  covers it, so `unsupported`.
- "Tuples are mutable." The tutorial says tuples are immutable, so `contradicted`.
- "In this lesson you will learn about dictionaries." Not a factual claim, so `not_applicable`.

## Dimension 2: citation correctness (claims from responses that cite)

Only applies where the response carries inline citations. Where the sheet already reads
`not_applicable`, leave it.

| Label | Use when |
|---|---|
| `correct` | A citation is attached and the passage it points to supports the claim. |
| `misattributed` | A citation is attached but that passage does not support the claim, even if some other passage would. |
| `missing` | The claim needs attribution (it is a factual claim about Python drawn from the materials) and none is attached. |
| `not_applicable` | The claim itself is `not_applicable` under dimension 1. |

A claim can be `supported` and `misattributed` at the same time: the corpus backs it, but the source
the system pointed at does not. That combination is the reason the two dimensions are separate.

## Dimension 3: supported by the retrieved passages (secondary, grounded responses only)

`yes`, `no` or `not_applicable`: does the claim follow from the passages **this response was given**,
listed in `contexts.json`? Leave blank where the response retrieved nothing.

The gap between dimension 1 and dimension 3 tells us whether the model used what it was handed, which
is a different question from whether the claim is true.

## Procedure

1. **Pilot.** Both raters label the same 20 claims independently. Then compare, discuss every
   disagreement, and amend this guide. Pilot claims are discarded, not reused.
2. **Main pass.** Both raters label the full sample independently, without discussion.
3. **Agreement.** Report Cohen's kappa per dimension with raw agreement, and the confusion matrix:
   ```bash
   .venv/bin/python -m src.experiment.annotation score --pack data/annotation/main --raters anas baidaa
   ```
4. **Adjudication.** Resolve disagreements by discussion, record how many needed it, and report that
   number in the paper.

## Blinding

The rating sheets carry no model or condition column: you cannot tell which backend produced a
response. You will often be able to tell the *condition* from the text itself (one condition has no
citations at all, another is formatted differently). That is unavoidable and the paper says so.
Please do not look up the key, and do not let a guess about the condition influence a label.

## Practical notes

- Work in `ratings_<yourname>.csv`. Fill `claim_support`, `citation_correctness`,
  `supported_by_retrieved`, and use `rater_note` for anything the labels cannot express.
- Do not reorder or delete rows; the claim ids join the two sheets.
- Write the labels as the guide spells them. Capitals and stray spaces are forgiven, so "Supported"
  and " supported " are the same label, but anything that is not a label at all is refused with the
  claim named, rather than being counted as a category of its own and quietly lowering our agreement.
- A half-finished sheet is fine. Agreement is computed over the claims we have both rated.
- Keep a rough note of how long a batch takes. Sizing the main sample depends on it (D16).
- If you find yourself unsure between two labels more than occasionally, stop and raise it: the guide
  is wrong, not you.
