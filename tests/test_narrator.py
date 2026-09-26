from reflex_harness.narrator import forbidden_tokens, validate_narrative
from reflex_harness.runner import load_task

TASK = load_task("osc-dev-01")
SYMBOLS = "apply_tax test_refund_total_keeps_cents TypeError"
FORBIDDEN = forbidden_tokens(TASK.repo, TASK.allowlist, SYMBOLS)


def test_structural_narrative_passes():
    text = ("A shared helper is called by two modules that pass amounts in different units. "
            "Each edit to the helper satisfied one caller and broke the other, and the agent "
            "reverted between the two behaviors.")
    assert validate_narrative(text, FORBIDDEN) == []


def test_domain_nouns_from_file_names_rejected():
    v = validate_narrative("Fixing the refund path broke invoices.", FORBIDDEN)
    assert "task term: 'refund'" in v
    assert "task term: 'invoices'" in v


def test_identifiers_rejected():
    v = validate_narrative("The agent edited apply_tax in billing/tax.py and hit TypeError.", FORBIDDEN)
    assert any(x.startswith("snake_case identifier") for x in v)
    assert any(x.startswith("file name") for x in v)
    assert any(x.startswith("path separator") for x in v)
    assert any(x.startswith("CamelCase identifier") for x in v)


def test_forbidden_includes_defined_names_and_symbols():
    assert {"refund_total_dollars", "invoice_summary", "lineitem", "apply_tax",
            "billing", "refund", "invoice", "tax", "typeerror"} <= FORBIDDEN
