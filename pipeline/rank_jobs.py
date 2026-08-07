"""Rank joblist.md ads by TF-IDF cosine similarity against master_cv.md.

No LLM calls — just page fetches + stdlib math. Run with:
    python -m pipeline.rank_jobs
"""
import math
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from updater import JOBLIST_PATH, ROOT, parse_table

CV_PATH = ROOT / "jobsearch" / "cv" / "master_cv.md"

STOPWORDS = {
    "och", "att", "det", "som", "for", "med", "till", "den", "the", "and",
    "for", "you", "our", "are", "har", "kan", "din", "sin", "ett", "ska",
    "via", "från", "into", "will", "med", "hos", "vid", "vara", "eller",
}


def tokenize(text):
    return [
        w for w in re.findall(r"[a-zA-ZåäöÅÄÖ]+", text.lower())
        if len(w) > 2 and w not in STOPWORDS
    ]


def tf(tokens):
    counts = Counter(tokens)
    total = sum(counts.values()) or 1
    return {w: n / total for w, n in counts.items()}


def idf(doc_tokens):
    n = len(doc_tokens)
    df = Counter()
    for tokens in doc_tokens:
        for w in set(tokens):
            df[w] += 1
    return {w: math.log(n / d) for w, d in df.items()}


def tfidf_vector(tokens, idf_map):
    return {w: v * idf_map.get(w, 0) for w, v in tf(tokens).items()}


def cosine(a, b):
    common = set(a) & set(b)
    numerator = sum(a[w] * b[w] for w in common)
    norm_a = math.sqrt(sum(v * v for v in a.values()))
    norm_b = math.sqrt(sum(v * v for v in b.values()))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return numerator / (norm_a * norm_b)


def score_documents(cv_text, doc_texts):
    """TF-IDF cosine similarity of cv_text against each of doc_texts, in order.
    Pure function — callers are responsible for fetching doc_texts, so this
    can score already-fetched page text without any network call of its own."""
    cv_tokens = tokenize(cv_text)
    doc_tokens = [tokenize(t) for t in doc_texts]

    idf_map = idf([cv_tokens] + doc_tokens)
    cv_vec = tfidf_vector(cv_tokens, idf_map)

    return [cosine(cv_vec, tfidf_vector(tokens, idf_map)) for tokens in doc_tokens]


def rank_jobs(cv_text, rows, fetch):
    valid_rows = []
    doc_texts = []
    for row in rows:
        url = (row.get("URL") or "").strip()
        if not url:
            continue
        text = fetch(url)
        if not text:
            continue
        valid_rows.append(row)
        doc_texts.append(text)

    scores = score_documents(cv_text, doc_texts)

    scored = list(zip(scores, valid_rows))
    scored.sort(key=lambda pair: -pair[0])
    return scored


def main():
    from search import fetch_page_text  # local import — avoids a circular
    # import with search.py, which imports score_documents from this module.

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    cv_text = CV_PATH.read_text(encoding="utf-8")
    rows, _ = parse_table(JOBLIST_PATH.read_text(encoding="utf-8").splitlines())

    scored = rank_jobs(cv_text, rows, fetch=fetch_page_text)

    print(f"{'#':<4}{'Score':<8}{'Företag':<35}{'Roll/Typ':<45}")
    for i, (score, row) in enumerate(scored, 1):
        company = (row.get("Företag") or "")[:33]
        role = (row.get("Roll/Typ") or "")[:43]
        print(f"{i:<4}{score:.3f}   {company:<35}{role:<45}")


if __name__ == "__main__":
    main()
