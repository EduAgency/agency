"""Keeps the frontend's e2e fixtures honest about what this API returns.

The Playwright suite serves a seeded fixture API instead of running Django, so
that accessibility tests scan rendered pages without needing Postgres, Redis and
a migration step in CI. That trade has exactly one failure mode: the fixtures
drift, and a page that is broken against the real API keeps passing its tests.

This closes that. ``FIELD_CONTRACT`` in ``frontend/e2e/fixtures/data.ts`` lists,
per serializer, every field the fixtures mock. Each one must exist on the real
serializer. Rename or drop a serializer field and this test fails, pointing at
the fixture that still believes in it.

It asserts "every field we mock is real", not "we mock every field" — the
frontend deliberately consumes a subset, and forcing fixtures to carry unused
fields would make them harder to read for no benefit.

See docs/enterprise-readiness.md, Phase 3.
"""

from __future__ import annotations

import json
import re
import subprocess
from importlib import import_module
from pathlib import Path

import pytest

FIXTURES = (
    Path(__file__).resolve().parents[2] / "frontend" / "e2e" / "fixtures" / "data.ts"
)


def _serializer_fields(dotted_path: str) -> set[str]:
    module_path, class_name = dotted_path.rsplit(".", 1)
    serializer_class = getattr(import_module(module_path), class_name)
    return set(serializer_class().fields.keys())


def _load_contract() -> dict[str, list[str]]:
    """Read FIELD_CONTRACT out of the TypeScript fixture file.

    Node is used when it is available, because it evaluates the real module and
    therefore cannot disagree with what Playwright loads. Where Node is absent —
    a backend-only CI image, for instance — the test skips rather than falling
    back to a regex that could quietly assert the wrong thing.
    """
    if not FIXTURES.exists():
        pytest.skip(f"Frontend fixtures not present at {FIXTURES}")

    script = (
        "const p=process.argv[1];"
        "const src=require('fs').readFileSync(p,'utf8');"
        # Strip TypeScript-only syntax the plain Node parser will not accept.
        "const js=src.replace(/^import .*$/gm,'')"
        ".replace(/export const/g,'const')"
        ".replace(/export function/g,'function')"
        ".replace(/: Record<string, unknown>/g,'')"
        ".replace(/ as const/g,'');"
        # `const` inside eval is block-scoped to it, so the value has to be the
        # eval's final expression rather than read back afterwards.
        "console.log(JSON.stringify(eval(js+';FIELD_CONTRACT')));"
    )
    try:
        result = subprocess.run(
            ["node", "-e", script, str(FIXTURES)],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pytest.skip("Node is not available to evaluate the frontend fixtures")

    if result.returncode != 0:
        pytest.fail(f"Could not read FIELD_CONTRACT from {FIXTURES}:\n{result.stderr}")

    return json.loads(result.stdout)


@pytest.mark.django_db
def test_every_mocked_field_exists_on_its_serializer():
    contract = _load_contract()
    assert contract, "FIELD_CONTRACT is empty — the fixtures are asserting nothing."

    problems: list[str] = []
    for dotted_path, mocked in contract.items():
        real = _serializer_fields(dotted_path)
        for field in mocked:
            if field not in real:
                problems.append(
                    f"{dotted_path} has no field {field!r}, but the e2e fixtures mock it. "
                    f"Real fields: {sorted(real)}"
                )

    assert not problems, "Frontend fixtures have drifted from the API:\n" + "\n".join(problems)


@pytest.mark.django_db
def test_contract_covers_the_serializers_the_fixtures_imitate():
    """A fixture file that stopped listing a serializer would silently stop guarding it."""
    contract = _load_contract()
    expected = {
        "apps.applications.serializers.ChecklistItemSerializer",
        "apps.applications.serializers.StudentDocumentSerializer",
        "apps.applications.serializers.DocumentUploadSerializer",
        "apps.accounts.serializers.StudentProfileSerializer",
    }
    missing = expected - set(contract)
    assert not missing, f"FIELD_CONTRACT no longer covers: {sorted(missing)}"


def test_fixture_file_declares_why_it_is_checked():
    """Guards the explanation, so the next person does not delete the guard."""
    text = FIXTURES.read_text(encoding="utf-8") if FIXTURES.exists() else ""
    if not text:
        pytest.skip("Frontend fixtures not present")
    assert re.search(r"FIELD_CONTRACT", text), "FIELD_CONTRACT went missing from the fixtures."
