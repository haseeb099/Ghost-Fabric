"""Pre-approved PHOENIX catalog remains operator-gated."""

from app.phoenix_preapproved import load_preapproved_templates, preapproved_projection


def test_preapproved_templates_require_operator_confirm() -> None:
    catalog = load_preapproved_templates()
    assert catalog["templates"]
    assert all(item["requires_operator_confirm"] is True for item in catalog["templates"])


def test_preapproved_projection_never_auto_executes() -> None:
    projection = preapproved_projection()
    assert projection["auto_execute"] is False
    assert projection["schema_version"] == 1
