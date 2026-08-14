"""aplitrak.com (Experis/Manpower/Jefferson Wells ads) redirects via
<meta http-equiv="refresh">, not a real HTTP redirect, so requests never
follows it and the fetched page reads as empty."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.search import _meta_refresh_target as search_target  # noqa: E402
from app.app import _meta_refresh_target as app_target  # noqa: E402

APLITRAK_HTML = (
    '<!DOCTYPE html><html><head>'
    '<meta http-equiv="refresh" content="0;url=\'https://www.jeffersonwells.se/'
    'sv/jobb/domain/inkopare-upphandlare-alingsas-energi/52009?aplitrak_email=x\'">'
    '</head><img class="spinner" src="/images/spinner.gif"></html>'
)


def test_extracts_meta_refresh_target():
    target = search_target(APLITRAK_HTML, "https://www.aplitrak.com/?adid=x")
    assert target == "https://www.jeffersonwells.se/sv/jobb/domain/inkopare-upphandlare-alingsas-energi/52009?aplitrak_email=x"


def test_both_copies_agree():
    assert app_target(APLITRAK_HTML, "https://www.aplitrak.com/?adid=x") == \
        search_target(APLITRAK_HTML, "https://www.aplitrak.com/?adid=x")


def test_no_meta_refresh_returns_none():
    assert search_target("<html><body>Hello</body></html>", "https://example.com") is None


def test_relative_target_resolved_against_base_url():
    html = '<meta http-equiv="refresh" content="0;url=\'/jobs/123\'">'
    assert search_target(html, "https://example.com/redirect") == "https://example.com/jobs/123"
