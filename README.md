# Mortgage Policy Q&A Agent — NeMo Agent Toolkit (NAT)

Everything here has been tested end-to-end using a pure-Python fallback for the
curation step (no GPU/RAPIDS needed to try it), plus NAT-compatible agent code.
You install the real `nvidia-nat` and (optionally) `nemo-curator` libraries locally
to run the full pipeline.

## ⚠️ One thing to know before you start

**NeMo Curator had a major version rewrite.** The `Sequential` / `Modify` /
`PiiModifier` / `ExactDuplicates` class-based API used in `curator/clean_pipeline.py`
is the NeMo Curator **0.x** API. NeMo Curator's **1.x** line was rewritten around a
Ray-based `Pipeline`/`ProcessingStage` architecture, and those old imports don't
exist there. If you just run `pip install nemo-curator`, you'll likely get 1.x and
`run_with_nemo_curator()` will fail on import. Either pin an 0.x release
(`pip install "nemo-curator[text_cpu]==0.6.0"`) or check NeMo Curator's current
migration guide and port that one function to the new API. **This only affects the
optional real-Curator path** — the default pure-Python fallback needs no NeMo
Curator install at all and is what's used by default.

## Project structure

```
mortgage-nat-project/
├── data/
│   ├── raw_docs/
│   │   ├── mortgage_policy.txt        # sample policy doc (clean-ish)
│   │   └── mortgage_faq_raw.txt       # messy: dupes, PII, mojibake, boilerplate
│   └── clean_mortgage_data.jsonl      # OUTPUT of the curation step
├── curator/
│   └── clean_pipeline.py              # cleans raw_docs/ -> clean_mortgage_data.jsonl
├── agent/
│   ├── tools.py                       # policy_retriever + emi_calculator tools
│   └── workflow.yaml                  # NAT agent + eval configuration
├── eval/
│   └── eval_dataset.jsonl             # 10 test questions with expected answers
├── pyproject.toml                     # lets NAT auto-discover tools.py
├── requirements.txt
└── README.md
```

## Step 1 — Set up your environment

```bash
python3 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

Get a free NVIDIA API key at https://build.nvidia.com (needed for the NIM LLM
used in `workflow.yaml`), then:

```bash
export NVIDIA_API_KEY="your-key-here"
```

## Step 2 — Run the curation pipeline

```bash
python3 curator/clean_pipeline.py
```

This reads everything in `data/raw_docs/`, splits it into chunks, and writes
`data/clean_mortgage_data.jsonl`. Already verified in testing against the sample
data included here: **54 raw chunks → 46 final chunks** (6 were pure boilerplate
that disappeared entirely once `[nav]`/`[footer]` tags were stripped, 2 were exact
duplicates), mojibake like `â€“` was repaired to `-`, and 4 chunks had PII redacted
(a PAN number, two phone numbers, an application ID, an email address, and two
agent names). Re-run it any time after editing the raw files — it's deterministic.

To try the real NeMo Curator path instead of the bundled fallback: install
`nemo-curator[text_cpu]` (0.x — see the warning above), open
`curator/clean_pipeline.py`, and set `USE_NEMO_CURATOR = True`. The
`run_with_nemo_curator()` function is already written using Curator's
`Sequential`, `Modify`, `UnicodeReformatter`, `PiiModifier`, and `ExactDuplicates`
classes — note in its docstring that `PiiModifier`'s built-in entity types don't
cover PAN numbers or application IDs, so you'd extend it with a custom
`DocumentModifier` mirroring the regexes in the fallback.

## Step 3 — Replace the sample data with real content (optional, recommended)

The two files in `data/raw_docs/` are synthetic — good enough to run and demo,
but for a stronger submission swap in real public content (an actual bank's home
loan FAQ, RBI home loan guideline text, etc.), keeping some messy-on-purpose
qualities (duplicates, encoding issues) in at least one file so the curation step
has something real to fix — that's the part evaluators will want explained.

## Step 4 — Register the tools and run the agent

`agent/tools.py` defines two tools using NAT's `@register_function` decorator:

- **`policy_retriever`** — keyword-overlap search over the curated JSONL. No
  embeddings yet (see "Suggested improvements" below) — good enough for a
  working demo over a small corpus.
- **`emi_calculator`** — standard reducing-balance EMI formula, verified against
  hand-calculation (₹40L @ 8.75% / 20yr → ₹35,348/month; ₹25L @ 9.2% / 15yr →
  ₹25,655/month).

`pyproject.toml` registers `agent.tools` under NAT's `nat.plugins` entry point
group so NAT auto-discovers the `@register_function` definitions. Install the
project itself (editable) so that entry point is picked up:

```bash
pip install -e .
```

Then run the agent:

```bash
nat run --config_file agent/workflow.yaml --input "What CIBIL score do I need for a home loan?"
```

Try a few more:

```bash
nat run --config_file agent/workflow.yaml --input "Calculate EMI for a 40 lakh loan at 8.75% for 20 years"
nat run --config_file agent/workflow.yaml --input "My monthly income is Rs. 60,000, I already pay Rs. 8,000 EMI, and I want a Rs. 30 lakh loan at 8.75% for 20 years. Am I eligible, and if not what's the smallest change to qualify?"

nat run --config_file agent/workflow.yaml --input "What documents do self-employed applicants need?"
nat run --config_file agent/workflow.yaml --input "I took a 40 lakh loan at 8.75% for 20 years, paid 36 EMIs so far, and want to prepay Rs. 2,00,000 now. How much do I save?"
```

## Step 5 — Evaluate

```bash
nat eval --config_file agent/workflow.yaml --dataset eval/eval_dataset.jsonl
```

`eval/eval_dataset.jsonl` has 10 questions with expected answers, scored here
with NAT's `tunable_rag_evaluator` (no extra `ragas` install needed — swap in a
`ragas`-based evaluator in `workflow.yaml` if you'd rather use `AnswerAccuracy`/
`ResponseGroundedness`, but that requires `pip install "nvidia-nat[ragas]"`).

**Question q9 is intentionally a trick question** — it asks for a specific
application's status, which the agent has no way to know. A good agent should
decline rather than hallucinate an answer. Use this to demonstrate responsible
AI behavior in your report.

## Step 6 — Deploy and demo

```bash
nat serve --config_file agent/workflow.yaml
```

Connect the NeMo Agent Toolkit UI (github.com/NVIDIA/NeMo-Agent-Toolkit-UI) to
this endpoint, enable "Intermediate Steps" in settings, and demo live.
