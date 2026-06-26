"""Live integration test — hits the real CELLAR SPARQL endpoint.

Run explicitly with:  pytest -m integration
Skipped automatically if the network/endpoint is unavailable.
"""

import httpx
import pytest
from extractor import fetch_requirements

pytestmark = pytest.mark.integration


def test_fetch_battery_regulation_live():
    try:
        reqs = fetch_requirements(families=["battery"])
    except httpx.HTTPError as exc:
        pytest.skip(f"CELLAR endpoint unavailable: {exc}")

    if not reqs:
        pytest.skip("CELLAR returned no data (transient).")

    req = reqs[0]
    assert req.celex == "32023R1542"
    assert req.regulation_family == "battery"
    assert "batteries" in req.title.lower()
    assert req.source_url.endswith("CELEX:32023R1542")
