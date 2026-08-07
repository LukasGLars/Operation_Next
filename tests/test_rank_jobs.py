"""TF-IDF ranking must put the ad closest to the CV first, without any LLM call."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.rank_jobs import cosine, idf, rank_jobs, tf, tokenize  # noqa: E402


def test_tokenize_drops_short_words_and_stopwords():
    tokens = tokenize("Python and Excel for data-driven roles och det")
    assert "and" not in tokens
    assert "och" not in tokens
    assert "det" not in tokens
    assert "python" in tokens
    assert "excel" in tokens


def test_tf_sums_to_one():
    weights = tf(["python", "python", "excel"])
    assert abs(sum(weights.values()) - 1.0) < 1e-9
    assert weights["python"] > weights["excel"]


def test_idf_zero_for_term_in_every_doc():
    weights = idf([["python", "excel"], ["python", "sales"]])
    assert weights["python"] == 0.0
    assert weights["excel"] > 0.0


def test_cosine_of_identical_vectors_is_one():
    vec = {"python": 0.5, "excel": 0.5}
    assert abs(cosine(vec, vec) - 1.0) < 1e-9


def test_cosine_of_disjoint_vectors_is_zero():
    assert cosine({"python": 1.0}, {"sales": 1.0}) == 0.0


def test_rank_jobs_orders_closest_match_first():
    cv_text = "Python automation, pandas, data-driven decision-making, AI integration"
    rows = [
        {"Företag": "Bageri", "Roll/Typ": "Butiksbiträde", "URL": "https://x.se/1"},
        {"Företag": "TechCo", "Roll/Typ": "Python Developer", "URL": "https://x.se/2"},
    ]
    fake_pages = {
        "https://x.se/1": "Vi söker en glad person till vårt bageri, ingen erfarenhet krävs",
        "https://x.se/2": "Python automation and pandas experience for AI-driven data pipelines",
    }
    scored = rank_jobs(cv_text, rows, fetch=lambda url: fake_pages[url])
    assert scored[0][1]["Företag"] == "TechCo"
    assert scored[0][0] > scored[1][0]
