import json

from methods.cle_prompt_ablation.prompt_profiles import PROFILES, get_profile, render_generation_prompt
from methods.cle_prompt_ablation.run_prompt_matrix import _normalise_h_pass_row, _summary
from methods.sct_lifecycle_replay.local_codeseceval import load_frozen_run


def test_p00_preserves_existing_prompt():
    original = "Generate code.\nExperience: []"
    assert render_generation_prompt(original, [], get_profile("P00")) == original
    assert len(PROFILES) == 25
    assert len(set(PROFILES)) == 25


def test_card_controls_do_not_expose_original_card_content():
    from methods.cle_prompt_ablation.prompt_profiles import render_cards, profile_sha256

    cards = [{"invariant_id": "x", "principle": "SECRET_PRINCIPLE",
              "applicability": "only here", "negative_guardrail": "never there"}]
    assert "SECRET_PRINCIPLE" not in render_cards(cards, get_profile("P23"))
    assert "SECRET_PRINCIPLE" not in render_cards(cards, get_profile("P24"))
    assert "only here" not in render_cards(cards, get_profile("P06"))
    assert "never there" not in render_cards(cards, get_profile("P06"))
    assert cards[0]["principle"] == "SECRET_PRINCIPLE"
    assert profile_sha256(get_profile("P06")) == profile_sha256(get_profile("P06"))


def test_h_pass_row_keeps_measured_status_and_error():
    row = _normalise_h_pass_row({"task_id": 7, "state": "B", "functional": "pass",
                                 "security": "fail", "error": "", "code": "x = 1"}, "P00")
    assert row["evidence"]["functional"]["status"] == "pass"
    assert row["evidence"]["security"]["status"] == "fail"
    assert _summary([row])["four_state"] == {"B": 1}


def test_unmeasured_h_pass_is_not_counted_as_failure():
    row = _normalise_h_pass_row({"task_id": 8, "state": "D", "functional": "",
                                 "security": "", "error": "empty_code", "code": ""}, "P01")
    summary = _summary([row])
    assert summary["unmeasured"] == 1
    assert summary["four_state"] == {"unmeasured": 1}


def test_cle_freeze_metadata_accepts_its_native_hash(tmp_path):
    import hashlib

    frozen = tmp_path / "frozen"
    frozen.mkdir()
    data = '{"invariant_id":"x"}\n'
    (frozen / "m_star.jsonl").write_bytes(data.encode())
    (frozen / "freeze_metadata.json").write_text(json.dumps({
        "m_star_sha256": hashlib.sha256(data.encode()).hexdigest(),
        "feedback_channel": "disabled",
    }), encoding="utf-8")
    cards, _ = load_frozen_run(tmp_path)
    assert cards[0]["invariant_id"] == "x"
