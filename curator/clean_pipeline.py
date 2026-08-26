"""
clean_pipeline.py
==================

Cleans the raw mortgage policy / FAQ text in data/raw_docs/ and writes
data/clean_mortgage_data.jsonl.

Two code paths are provided:

1. Pure-Python fallback (default, USE_NEMO_CURATOR = False)
   No GPU / RAPIDS / nemo-curator install required. Reimplements, in plain
   Python, the same four operations the real pipeline performs:
     - Unicode/mojibake repair
     - Boilerplate ([nav]/[footer]) stripping
     - Exact-duplicate removal
     - PII redaction (PAN, phone numbers, application IDs, emails, names
       mentioned alongside "agent"/"contact")

2. Real NeMo Curator path (USE_NEMO_CURATOR = True)
   Uses actual nemo_curator classes: Sequential, Modify, UnicodeReformatter,
   PiiModifier, ExactDuplicates.

   IMPORTANT — version note: the Sequential/Modify/ScoreFilter "call an
   object on a DocumentDataset" API used below is the NeMo Curator 0.x API
   (the one shown in NVIDIA's own curation blog posts and the version this
   assignment's README was clearly written against). NeMo Curator's 1.x
   line rewrote the library around a Ray-based Pipeline/ProcessingStage
   architecture and the old imports below no longer exist there. If
   `pip install nemo-curator` pulls down a 1.x release, run_with_nemo_curator()
   below will fail on import. Pin an 0.x release, e.g.:
       pip install "nemo-curator[text_cpu]==0.6.0"
   or check the current NeMo Curator docs' migration guide and port this
   function to the new Pipeline/ProcessingStage API if you want to run on
   the latest release instead.
"""

import hashlib
import json
import re
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

USE_NEMO_CURATOR = False  # flip to True once nemo-curator is installed (see note above)

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "data" / "raw_docs"
OUTPUT_PATH = BASE_DIR / "data" / "clean_mortgage_data.jsonl"

# ---------------------------------------------------------------------------
# Step A — chunking
# ---------------------------------------------------------------------------


def load_raw_chunks(raw_dir: Path) -> list[dict]:
    """Read every .txt file in raw_dir and split it into blank-line-delimited chunks."""
    chunks = []
    for file_path in sorted(raw_dir.glob("*.txt")):
        text = file_path.read_text(encoding="utf-8")
        raw_pieces = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
        for i, piece in enumerate(raw_pieces):
            chunks.append({
                "id": f"{file_path.stem}-{i:03d}",
                "source_file": file_path.name,
                "text": piece,
            })
    return chunks


# ---------------------------------------------------------------------------
# Step B — mojibake / unicode repair
# ---------------------------------------------------------------------------

# Common UTF-8-decoded-as-Latin-1/CP1252 mojibake sequences seen in scraped web text.
_MOJIBAKE_MAP = {
    "â€“": "-",
    "â€”": "-",
    "â€™": "'",
    "â€˜": "'",
    "â€œ": '"',
    "â€\x9d": '"',
    "â€": '"',
    "Â©": "(c)",
    "Ã©": "e",
    "Ã¨": "e",
    "Ã—": "x",
    "Â ": " ",
}


def fix_mojibake(text: str) -> str:
    try:
        import ftfy  # type: ignore
        return ftfy.fix_text(text)
    except ImportError:
        for bad, good in _MOJIBAKE_MAP.items():
            text = text.replace(bad, good)
        return text


# ---------------------------------------------------------------------------
# Step C — boilerplate stripping
# ---------------------------------------------------------------------------

_BOILERPLATE_RE = re.compile(r"\[nav\].*?\[/nav\]|\[footer\].*?\[/footer\]", re.IGNORECASE | re.DOTALL)


def strip_boilerplate(text: str) -> str | None:
    cleaned = _BOILERPLATE_RE.sub("", text).strip()
    return cleaned if cleaned else None


# ---------------------------------------------------------------------------
# Step D — PII redaction
# ---------------------------------------------------------------------------

_PII_PATTERNS = {
    "PAN": re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b"),
    "PHONE": re.compile(r"\b[6-9]\d{4}[\s-]?\d{5}\b"),
    "APPLICATION_ID": re.compile(r"\bAPP-\d{4}-\d{4,6}\b"),
    "EMAIL": re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"),
    # "agent <Name>" / "Contact <Name> at" style mentions of staff names
    "AGENT_NAME": re.compile(r"\b(?:agent(?:\s+was|\s+is)?|Contact)\s+([A-Z][a-z]+\s[A-Z][a-z]+)\b"),
}


def redact_pii(text: str) -> tuple[str, list[str]]:
    found = []
    for label, pattern in _PII_PATTERNS.items():
        if label == "AGENT_NAME":
            def _sub(m):
                found.append(label)
                return m.group(0).replace(m.group(1), "[REDACTED_NAME]")
            text = pattern.sub(_sub, text)
        else:
            if pattern.search(text):
                found.append(label)
                text = pattern.sub(f"[REDACTED_{label}]", text)
    return text, found


# ---------------------------------------------------------------------------
# Step E — exact-duplicate removal
# ---------------------------------------------------------------------------


def dedupe_exact(chunks: list[dict]) -> list[dict]:
    seen = set()
    kept = []
    for c in chunks:
        key = hashlib.md5(c["text"].strip().lower().encode("utf-8")).hexdigest()
        if key not in seen:
            seen.add(key)
            kept.append(c)
    return kept


# ---------------------------------------------------------------------------
# Pure-Python pipeline (default)
# ---------------------------------------------------------------------------


def run_pure_python_pipeline() -> None:
    raw_chunks = load_raw_chunks(RAW_DIR)
    n_raw = len(raw_chunks)

    cleaned = []
    for c in raw_chunks:
        text = fix_mojibake(c["text"])
        text = strip_boilerplate(text)
        if text is None:
            continue  # was pure boilerplate, nothing left after stripping
        text, redactions = redact_pii(text)
        cleaned.append({**c, "text": text, "redactions": redactions})

    deduped = dedupe_exact(cleaned)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        for row in deduped:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    n_final = len(deduped)
    n_dropped_dupes = len(cleaned) - n_final
    n_dropped_boilerplate_only = n_raw - len(cleaned)
    n_with_redactions = sum(1 for r in deduped if r["redactions"])

    print(f"Raw chunks read:              {n_raw}")
    print(f"Dropped (pure boilerplate):   {n_dropped_boilerplate_only}")
    print(f"Dropped (exact duplicates):   {n_dropped_dupes}")
    print(f"Final chunks written:         {n_final}")
    print(f"Chunks with PII redacted:     {n_with_redactions}")
    print(f"Output written to:            {OUTPUT_PATH}")


# ---------------------------------------------------------------------------
# Real NeMo Curator pipeline (USE_NEMO_CURATOR = True)
# ---------------------------------------------------------------------------


def run_with_nemo_curator() -> None:
    """
    Real NeMo Curator 0.x pipeline. Requires:
        pip install "nemo-curator[text_cpu]==0.6.0"   (pin — see module docstring)
    """
    from nemo_curator import get_client, Sequential, Modify, ExactDuplicates
    from nemo_curator.datasets import DocumentDataset
    from nemo_curator.modifiers.pii_modifier import PiiModifier
    from nemo_curator.modifiers.unicode_reformatter import UnicodeReformatter
    from nemo_curator.utils.file_utils import get_all_files_paths_under
    import pandas as pd

    get_client(cluster_type="cpu")

    # Load raw chunks into a DocumentDataset via an intermediate pandas frame,
    # since our source files are plain .txt, not pre-chunked JSON.
    raw_chunks = load_raw_chunks(RAW_DIR)
    df = pd.DataFrame(raw_chunks)
    dataset = DocumentDataset.from_pandas(df)

    cleaning_pipeline = Sequential([
        Modify(UnicodeReformatter(), text_field="text"),
        Modify(
            PiiModifier(
                supported_entities=["PERSON", "PHONE_NUMBER", "EMAIL_ADDRESS"],
                anonymize_action="redact",
                device="cpu",
            ),
            text_field="text",
        ),
    ])
    dataset = cleaning_pipeline(dataset)

    deduplicator = ExactDuplicates(id_field="id", text_field="text")
    duplicate_ids = deduplicator(dataset)
    dataset = deduplicator.remove(dataset, duplicate_ids)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    dataset.to_json(str(OUTPUT_PATH.parent), write_to_filename=False)
    print(f"NeMo Curator pipeline complete. Output under: {OUTPUT_PATH.parent}")
    print("Note: PAN numbers, application IDs, and boilerplate [nav]/[footer] tags "
          "are NOT covered by PiiModifier's built-in entity types — add custom "
          "regex-based DocumentModifier subclasses for those, mirroring "
          "redact_pii()/strip_boilerplate() above.")


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if USE_NEMO_CURATOR:
        run_with_nemo_curator()
    else:
        run_pure_python_pipeline()
