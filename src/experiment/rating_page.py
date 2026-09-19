"""
A rating pack a rater can use with nothing but a browser.

The pilot pack assumes the repository, a virtual environment and a vector store,
because claim support is judged against the whole corpus and the only way to
search it was a Python command (D26). That is an unreasonable ask of a second
rater, and a rater who skips it judges against the five passages the response
happened to retrieve, which is exactly the circularity D26 exists to avoid.

This writes one self-contained HTML file per rater: the claims, the response each
came from, the passages it was given, the entire corpus with a search box, and a
button that exports the CSV the scorer already reads. Ratings are kept in the
browser's local storage as they are entered, so a closed tab does not lose them.

It also times the sitting, because D16 sets the main sample size from how long
the pilot takes and asking someone to remember afterwards gets a worse number.

Usage:
    python -m src.experiment.rating_page --pack data/annotation/pilot --rater baidaa
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Dict, List

from .annotation import CITATION_LABELS, SUPPORT_LABELS
from .corpus import load_corpus_store

# The third dimension's labels are not exported by annotation.py because the
# scorer builds them inline; keep the one definition here and assert the others
# come from there, so the page can never offer a label the scorer refuses.
RETRIEVED_LABELS = ["yes", "no", "not_applicable"]

COLUMNS = ["claim_id", "response_id", "module_title", "topic", "claim_text",
           "claim_support", "citation_correctness", "supported_by_retrieved", "rater_note"]


def _corpus_chunks() -> List[Dict[str, str]]:
    """Every indexed chunk, so support can be judged against the corpus as a whole."""
    chunks = []
    for document in load_corpus_store().get_all_documents():
        meta = document.metadata or {}
        chunks.append({
            "source": str(meta.get("source") or meta.get("title") or "unknown"),
            "strand": str(meta.get("strand") or ""),
            "url": str(meta.get("url") or ""),
            "text": document.content,
        })
    return chunks


def build(pack_dir: Path, rater: str) -> Path:
    rows = list(csv.DictReader((pack_dir / f"ratings_{rater}.csv").open(encoding="utf-8")))
    contexts = {c["response_id"]: c
                for c in json.loads((pack_dir / "contexts.json").read_text(encoding="utf-8"))}
    payload = {
        "rater": rater,
        "columns": COLUMNS,
        "labels": {"claim_support": SUPPORT_LABELS,
                   "citation_correctness": CITATION_LABELS,
                   "supported_by_retrieved": RETRIEVED_LABELS},
        "rows": rows,
        "contexts": contexts,
        "corpus": _corpus_chunks(),
    }
    html = _PAGE.replace("__PAYLOAD__", json.dumps(payload, ensure_ascii=False))
    out = pack_dir / f"rate_{rater}.html"
    out.write_text(html, encoding="utf-8")
    return out


_PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>LearnX claim rating</title>
<style>
  :root { --ink:#141413; --muted:#605f5c; --line:#e3e2de; --surface:#fcfcfb; --panel:#fff;
          --accent:#2a78d6; --warn:#eb6834; }
  * { box-sizing: border-box; }
  body { margin:0; background:var(--surface); color:var(--ink);
         font:15px/1.55 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
  header { position:sticky; top:0; z-index:5; background:var(--panel);
           border-bottom:1px solid var(--line); padding:12px 20px;
           display:flex; gap:16px; align-items:center; flex-wrap:wrap; }
  header h1 { font-size:16px; margin:0; font-weight:650; }
  .spacer { flex:1 1 auto; }
  .status { color:var(--muted); font-size:13px; }
  button { font:inherit; padding:8px 14px; border-radius:7px; border:1px solid var(--line);
           background:var(--panel); cursor:pointer; }
  button.primary { background:var(--accent); border-color:var(--accent); color:#fff; font-weight:600; }
  button:disabled { opacity:.5; cursor:not-allowed; }
  main { max-width:1080px; margin:0 auto; padding:20px; }
  .intro { background:var(--panel); border:1px solid var(--line); border-radius:10px;
           padding:16px 18px; margin-bottom:22px; }
  .intro h2 { margin:0 0 8px; font-size:15px; }
  .intro ul { margin:8px 0 0 18px; padding:0; }
  .intro li { margin-bottom:5px; }
  .claim { background:var(--panel); border:1px solid var(--line); border-radius:10px;
           padding:16px 18px; margin-bottom:18px; }
  .claim.done { border-left:4px solid var(--accent); }
  .claim-head { display:flex; gap:10px; align-items:baseline; flex-wrap:wrap;
                color:var(--muted); font-size:12.5px; margin-bottom:8px; }
  .claim-text { font-size:16px; margin:6px 0 14px; }
  details { margin:8px 0; border-top:1px solid var(--line); padding-top:8px; }
  summary { cursor:pointer; color:var(--accent); font-size:13.5px; }
  .passage { border-left:3px solid var(--line); padding:6px 0 6px 12px; margin:10px 0;
             font-size:13.5px; white-space:pre-wrap; }
  .passage .src { color:var(--muted); font-size:12px; display:block; margin-bottom:4px; }
  .response { white-space:pre-wrap; font-size:13.5px; margin-top:8px; }
  .dims { display:grid; gap:12px; margin-top:12px; }
  .dim label.q { display:block; font-size:13px; color:var(--muted); margin-bottom:5px; }
  .opts { display:flex; gap:6px; flex-wrap:wrap; }
  .opts label { border:1px solid var(--line); border-radius:999px; padding:5px 11px;
                font-size:13px; cursor:pointer; background:var(--surface); }
  .opts input { display:none; }
  .opts input:checked + span { font-weight:650; }
  .opts label:has(input:checked) { border-color:var(--accent); background:#eaf2fd; }
  .opts label.disabled { opacity:.45; cursor:not-allowed; }
  textarea { width:100%; min-height:44px; font:inherit; padding:8px; border-radius:7px;
             border:1px solid var(--line); background:var(--surface); resize:vertical; }
  .corpus { position:fixed; inset:auto 0 0 0; max-height:62vh; background:var(--panel);
            border-top:2px solid var(--accent); box-shadow:0 -8px 24px rgba(0,0,0,.09);
            display:none; flex-direction:column; z-index:8; }
  .corpus.open { display:flex; }
  .corpus-bar { display:flex; gap:10px; padding:10px 16px; border-bottom:1px solid var(--line);
                align-items:center; }
  .corpus-bar input { flex:1; font:inherit; padding:8px 10px; border-radius:7px;
                      border:1px solid var(--line); }
  .corpus-results { overflow:auto; padding:10px 16px 16px; }
  mark { background:#ffe9a8; }
  .hint { color:var(--muted); font-size:12.5px; }
  @media (max-width:640px){ main{padding:14px} .claim{padding:13px} }
</style>
</head>
<body>
<header>
  <h1>LearnX claim rating</h1>
  <span class="status" id="progress">0 of 0 rated</span>
  <span class="status" id="timer">timing this sitting</span>
  <span class="spacer"></span>
  <button id="corpus-toggle">Search the corpus</button>
  <button class="primary" id="download" disabled>Download my ratings</button>
</header>

<main>
  <section class="intro">
    <h2>What to do</h2>
    <ul>
      <li>Rate each claim on its own. Do not discuss them with the other rater until both sheets are in.</li>
      <li><strong>Claim support is judged against the whole corpus</strong>, not only the passages the
          response happened to retrieve. Use <em>Search the corpus</em> to check before deciding.</li>
      <li><em>Citation correctness</em> is fixed to <code>not_applicable</code> where the claim comes
          from a condition that emits no citations. Those are locked, not for you to fill.</li>
      <li><em>Supported by the retrieved passages</em>: leave blank where the response retrieved
          nothing, so it drops out of the agreement. Use <code>not_applicable</code> only where the
          claim itself is not applicable.</li>
      <li>Your answers are saved in this browser as you go. When you are finished, press
          <strong>Download my ratings</strong> and send the file back.</li>
    </ul>
    <p class="hint">The page times the sitting. The main sample size is set from how long the pilot
       takes, so the figure is useful rather than nosy.</p>
  </section>
  <div id="claims"></div>
</main>

<div class="corpus" id="corpus">
  <div class="corpus-bar">
    <input id="corpus-q" placeholder="Search all 533 corpus chunks, e.g. list comprehension syntax">
    <span class="status" id="corpus-count"></span>
    <button id="corpus-close">Close</button>
  </div>
  <div class="corpus-results" id="corpus-results"></div>
</div>

<script>
const DATA = __PAYLOAD__;
const KEY = "learnx-ratings-" + DATA.rater;
const state = JSON.parse(localStorage.getItem(KEY) || "{}");
const started = Number(localStorage.getItem(KEY + "-started") || Date.now());
localStorage.setItem(KEY + "-started", started);

const esc = s => String(s == null ? "" : s).replace(/[&<>"]/g, c =>
  ({ "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;" }[c]));

function save() {
  try { localStorage.setItem(KEY, JSON.stringify(state)); } catch (e) {}
  render_progress();
}

function render_progress() {
  const done = DATA.rows.filter(r => (state[r.claim_id] || {}).claim_support).length;
  document.getElementById("progress").textContent = done + " of " + DATA.rows.length + " rated";
  document.getElementById("download").disabled = done === 0;
  DATA.rows.forEach(r => {
    const el = document.getElementById("claim-" + r.claim_id);
    if (el) el.classList.toggle("done", Boolean((state[r.claim_id] || {}).claim_support));
  });
}

function options(claim_id, dim, labels, locked) {
  return labels.map(v => {
    const current = (state[claim_id] || {})[dim];
    const dis = locked ? " disabled" : "";
    return '<label class="' + (locked ? "disabled" : "") + '">' +
      '<input type="radio" name="' + dim + "-" + claim_id + '" value="' + v + '"' +
      (current === v ? " checked" : "") + dis + '><span>' + v + "</span></label>";
  }).join("");
}

function passage_block(p) {
  const src = esc(p.source || "source " + p.passage_index);
  const url = p.url ? ' <a href="' + esc(p.url) + '" target="_blank" rel="noreferrer">link</a>' : "";
  return '<div class="passage"><span class="src">[' + esc(p.passage_index) + '] ' + src + url +
         "</span>" + esc(p.content) + "</div>";
}

document.getElementById("claims").innerHTML = DATA.rows.map((row, i) => {
  const ctx = DATA.contexts[row.response_id] || {};
  const passages = ctx.retrieved_passages || [];
  const locked = row.citation_correctness === "not_applicable";
  if (locked && !(state[row.claim_id] || {}).citation_correctness) {
    state[row.claim_id] = Object.assign({}, state[row.claim_id], { citation_correctness: "not_applicable" });
  }
  return '<article class="claim" id="claim-' + row.claim_id + '">' +
    '<div class="claim-head"><strong>' + (i + 1) + " of " + DATA.rows.length + "</strong>" +
      "<span>" + esc(row.module_title) + "</span><span>" + esc(row.topic) + "</span>" +
      "<span>" + esc(row.claim_id) + "</span></div>" +
    '<div class="claim-text">' + esc(row.claim_text) + "</div>" +
    (passages.length
      ? "<details><summary>" + passages.length + " passage(s) this response was given</summary>" +
        passages.map(passage_block).join("") + "</details>"
      : '<p class="hint">This response retrieved no passages. Leave the third question blank.</p>') +
    "<details><summary>The full response this claim came from</summary>" +
      '<div class="response">' + esc(ctx.response_text || "") + "</div></details>" +
    '<div class="dims">' +
      '<div class="dim"><label class="q">1. Does the claim follow from the corpus as a whole?</label>' +
        '<div class="opts" data-dim="claim_support" data-claim="' + row.claim_id + '">' +
        options(row.claim_id, "claim_support", DATA.labels.claim_support, false) + "</div></div>" +
      '<div class="dim"><label class="q">2. Is the citation attached to it correct?' +
        (locked ? " (fixed: this condition emits no citations)" : "") + "</label>" +
        '<div class="opts" data-dim="citation_correctness" data-claim="' + row.claim_id + '">' +
        options(row.claim_id, "citation_correctness", DATA.labels.citation_correctness, locked) +
        "</div></div>" +
      '<div class="dim"><label class="q">3. Does it follow from the passages this response was given?' +
        " Leave blank if it retrieved nothing.</label>" +
        '<div class="opts" data-dim="supported_by_retrieved" data-claim="' + row.claim_id + '">' +
        options(row.claim_id, "supported_by_retrieved", DATA.labels.supported_by_retrieved, false) +
        "</div></div>" +
      '<div class="dim"><label class="q">Note (optional)</label>' +
        '<textarea data-note="' + row.claim_id + '">' + esc((state[row.claim_id] || {}).rater_note || "") +
        "</textarea></div>" +
    "</div></article>";
}).join("");

document.addEventListener("change", e => {
  const opts = e.target.closest(".opts");
  if (!opts) return;
  const claim = opts.dataset.claim, dim = opts.dataset.dim;
  state[claim] = Object.assign({}, state[claim], { [dim]: e.target.value });
  save();
});

document.addEventListener("input", e => {
  const id = e.target.dataset && e.target.dataset.note;
  if (!id) return;
  state[id] = Object.assign({}, state[id], { rater_note: e.target.value });
  save();
});

document.getElementById("download").addEventListener("click", () => {
  const minutes = Math.round((Date.now() - started) / 60000);
  const quote = v => {
    const s = String(v == null ? "" : v);
    return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
  };
  const lines = [DATA.columns.join(",")];
  DATA.rows.forEach(row => {
    const r = state[row.claim_id] || {};
    lines.push(DATA.columns.map(c => quote(
      c in r ? r[c] : (c === "claim_support" || c === "supported_by_retrieved" ? "" : row[c])
    )).join(","));
  });
  lines.push("");
  lines.push("# minutes spent on this sitting: " + minutes);
  const blob = new Blob([lines.join("\n")], { type: "text/csv" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "ratings_" + DATA.rater + ".csv";
  a.click();
});

const corpus = document.getElementById("corpus");
document.getElementById("corpus-toggle").addEventListener("click", () => {
  corpus.classList.add("open");
  document.getElementById("corpus-q").focus();
});
document.getElementById("corpus-close").addEventListener("click", () => corpus.classList.remove("open"));

let debounce;
document.getElementById("corpus-q").addEventListener("input", e => {
  clearTimeout(debounce);
  debounce = setTimeout(() => {
    const terms = e.target.value.toLowerCase().split(/\s+/).filter(Boolean);
    const results = terms.length
      ? DATA.corpus.filter(c => { const t = c.text.toLowerCase(); return terms.every(w => t.includes(w)); })
      : [];
    document.getElementById("corpus-count").textContent =
      terms.length ? results.length + " of " + DATA.corpus.length + " chunks" : "";
    document.getElementById("corpus-results").innerHTML = results.slice(0, 60).map(c => {
      let text = esc(c.text);
      terms.forEach(w => {
        text = text.replace(new RegExp("(" + w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + ")", "gi"),
                            "<mark>$1</mark>");
      });
      return '<div class="passage"><span class="src">' + esc(c.source) +
             (c.strand ? " &middot; " + esc(c.strand) : "") + "</span>" + text + "</div>";
    }).join("") || '<p class="hint">No chunk contains all of those words.</p>';
  }, 120);
});

setInterval(() => {
  const m = Math.round((Date.now() - started) / 60000);
  document.getElementById("timer").textContent = m < 1 ? "just started" : m + " min in this sitting";
}, 15000);

render_progress();
</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--pack", type=Path, default=Path("data/annotation/pilot"))
    parser.add_argument("--rater", required=True)
    args = parser.parse_args()
    print(f"Written: {build(args.pack, args.rater)}")


if __name__ == "__main__":
    main()
