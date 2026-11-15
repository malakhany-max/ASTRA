from hub.content import load_plan_content


def test_plan_adapter_reads_companion_owned_content():
    content = load_plan_content()
    assert content["source"]
    assert content["exercise"]
    assert content["nutrition"]
    assert content["exercise"][0]["notes"]
    assert "TO BE FILLED" not in content["exercise"][0]["notes"]


def test_missing_plan_content_uses_engine_placeholders(tmp_path):
    assert load_plan_content(tmp_path / "missing.yaml") == {}
