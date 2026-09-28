# Annotation guide: claim support and citation correctness

**Version 0.2, 28 September 2026.** Amended after the pilot. Dimension 2 is rewritten: it produced
kappa = 0.079 across 16 claims, with all 11 disagreements the same shape, one rater reading the
question as "does this claim carry a citation" and the other as "does the response cite acceptably".
Dimensions 1 and 3 are unchanged (kappa 0.496 and 0.818). Pilot claims are discarded.

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

Search the corpus rather than reading it end to end. The browser sheet has a **Search the corpus**
button that does this with no setup. From the repository the same search is:

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

## Dimension 2: citation correctness (every factual claim)

**Start by looking at the claim itself for a citation marker**, something like `[3]` or `[1, 3]`.
This dimension is about *this claim*, not about the response's citing habits. A response that cites
well in other paragraphs does not make an uncited claim `correct`. That single confusion produced
every disagreement in the pilot.

| Label | Use when |
|---|---|
| `correct` | A marker is on this claim **and** the passage it points to supports the claim. |
| `misattributed` | A marker is on this claim **but** the passage it points to does not support it, even if some other passage would. Also use this where the marker points to a passage that does not exist, which happens in the condition that retrieves nothing. |
| `uncited` | No marker on this claim, and the claim is a factual statement about Python that should have carried one. (Called `missing` in version 0.1.) |
| `not_applicable` | The claim is `not_applicable` under dimension 1, **or** the response retrieved nothing and this claim carries no marker, so there was no source it could have pointed at. |

Decision order, which removes the ambiguity:

1. Is the claim `not_applicable` under dimension 1? Then `not_applicable`.
2. Does the claim carry a marker? If yes, check the passage it names: supporting is `correct`,
   not supporting, or naming a passage that was never supplied, is `misattributed`.
3. No marker, and the response was given passages? Then `uncited`.
4. No marker, and the response was given no passages at all? Then `not_applicable`.

Step 2's "passage that was never supplied" is not hypothetical. In the ungrounded condition 541 of
919 responses carry citation markers despite having been given no passages whatsoever, 6,157 markers
in total. Those are fabricated attributions and they should be recorded as `misattributed`.

A claim can be `supported` and `uncited` at the same time, and that pairing is common: the corpus
backs the claim, and the system simply did not attribute it. It can equally be `supported` and
`misattributed`: the corpus backs it, but the source pointed at does not. Both combinations are why
the two dimensions are kept separate.

## Dimension 3: supported by the retrieved passages (secondary, grounded responses only)

`yes`, `no` or `not_applicable`: does the claim follow from the passages **this response was given**,
listed in `contexts.json`?

Two cases are not the same and should not be filled in the same way. Where the response retrieved
nothing at all, so there is no passage to judge against, leave the cell **blank**: it drops out of
the agreement entirely, which is right, because there was nothing for either of us to disagree
about. Use `not_applicable` only where dimension 1 was `not_applicable`, so that we still record
having looked.

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

- Work in your own browser sheet, `data/annotation/pilot/rate_<yourname>.html`. Open it in any
  browser; nothing needs installing and it works offline. It holds the claims, each full response,
  the passages that response was given, and the corpus with a search box, and it exports the CSV
  when you are done. There is no blank spreadsheet to fill in: judging support against the whole
  corpus needs the corpus to hand, which the browser sheet carries and a CSV does not.
- Your answers are kept in the browser as you type, so a closed tab does not lose them.
- Write the labels as the guide spells them. Capitals and stray spaces are forgiven, so "Supported"
  and " supported " are the same label, but anything that is not a label at all is refused with the
  claim named, rather than being counted as a category of its own and quietly lowering our agreement.
- A half-finished sheet is fine. Agreement is computed over the claims we have both rated.
- Keep a rough note of how long a batch takes. The size of the main sample is set from that figure.
- If you find yourself unsure between two labels more than occasionally, stop and raise it: the guide
  is wrong, not you.
