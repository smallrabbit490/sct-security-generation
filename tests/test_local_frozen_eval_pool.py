import json

from methods.sct_trajectory.run_local_frozen_eval import freeze_mstar


def test_freeze_mstar_reads_pool_and_excludes_retired(tmp_path):
    run = tmp_path / "run"
    (run / "frozen").mkdir(parents=True)
    (run / "tree.json").write_text("{}", encoding="utf-8")
    rows = [
        {"invariant_id": "keep", "status": "provisional", "cwe": "79",
         "positive_principle": "Escape output", "applicability": "HTML"},
        {"invariant_id": "drop", "status": "retired", "cwe": "79",
         "positive_principle": "Unsafe advice"},
    ]
    (run / "frozen" / "m_star.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
    )

    cards = freeze_mstar(run, tmp_path / "out", model="test-model")

    assert [card["id"] for card in cards] == ["keep"]
    assert cards[0]["principle"] == "Escape output"
