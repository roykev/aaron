"""Open the built HTML offline in headless Chromium: no console errors, no network, tiles match analysis.dims.
Skipped when Playwright is not installed (pip install -e ".[browser]" && playwright install chromium)."""
import json
from pathlib import Path

import pytest

from course_reports import cli

pw = pytest.importorskip("playwright.sync_api")
EX = Path(__file__).resolve().parents[1] / "examples"


@pytest.fixture(scope="module")
def browser():
    with pw.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as e:  # browser binary not downloaded
            pytest.skip(f"chromium unavailable: {e}")
        yield b
        b.close()


@pytest.mark.parametrize("name", ["psychology", "informal"])
def test_html_opens_offline_without_errors(name, browser, tmp_path):
    args = ["build", "--reports", str(EX / name / "export.json"), "--course", str(EX / name / "course.json"),
            "--out", str(tmp_path), "--slug", name, "--format", "html", "--no-llm"]
    if (EX / name / "learning_report.md").exists():
        args += ["--learned", str(EX / name / "learning_report.md")]
    cli.main(args)
    analysis = json.loads((tmp_path / f"{name}.analysis.json").read_text(encoding="utf-8"))

    page = browser.new_page()
    errors, requests = [], []
    page.on("console", lambda m: m.type == "error" and errors.append(m.text))
    page.on("pageerror", lambda e: errors.append(str(e)))

    def block(route):
        requests.append(route.request.url)
        route.abort()
    page.route("http*://**/*", block)
    page.goto((tmp_path / f"{name}.html").as_uri())
    page.wait_for_selector(".tile", state="attached")

    assert page.locator(".tile").count() == 16
    for d, v in analysis["dims"].items():
        cls = page.locator(f"#dim-{d}").get_attribute("class")
        assert v["level"] in cls.split(), (d, cls, v["level"])
    first = analysis["_meta"]["facts"]["course"]["lesson_numbers"][0]
    page.goto((tmp_path / f"{name}.html").as_uri() + f"#l{first}")
    page.wait_for_timeout(200)
    assert not errors, errors
    assert not requests, f"the report fetched from the network: {requests}"
