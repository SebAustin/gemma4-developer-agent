"""Draw ledger: parsing the Kaggle submissions listing, Failed draws, slot rotation."""

from __future__ import annotations

from datetime import date

import pytest

from g4agent.draws import (
    LedgerError,
    SlotConfig,
    build_ledger,
    next_draw,
    read_ledger,
    report,
    write_ledger,
)

HEADER = "ref,fileName,date,description,status,publicScore,privateScore\n"
WARNING = "Warning: Looks like you're using an outdated `kaggle` version (installed: 2.2.3)\n"

V5 = "v5_budgetfit a975adbcd250"
V8 = "v8_temp1 15e1bb7b9357"
SUFFIX = "harness swegemma 0.2.11 (attribution in submissions/ATTRIBUTION.md)"


def _row(ref, when, desc, status="COMPLETE", score="0.17"):
    return f'{ref},submission.zip,{when},"{desc}",SubmissionStatus.{status},{score},\n'


def _daily(label, kernel, n):
    return f"{label}, kernel v{kernel}, daily draw {n}, {SUFFIX}"


SLOT = SlotConfig.from_dict(
    {
        "competition": "gemma-4-developer-agent",
        "kernel": "sebmontreal/g4-submission",
        "public_tasks": 58,
        "pause": False,
        "description_suffix": SUFFIX,
        "kernels": {
            8: {"bundle": "v5_budgetfit", "hash": "a975adbcd250"},
            9: {"bundle": "v8_temp1", "hash": "15e1bb7b9357"},
        },
        "rotation": [8, 9],
        "backfill": {"58109075": {"draw": 1, "kernel": 8}, "58222745": {"draw": 3, "kernel": 8}},
    }
)


def _listing(*rows, warning=True):
    return (WARNING if warning else "") + HEADER + "".join(rows)


HISTORY = _listing(
    _row(58419360, "2026-11-16 06:23:40.4", _daily(V8, 9, 7), score="0.17"),
    _row(58379290, "2026-11-15 09:52:18.1", _daily(V5, 8, 6), score="0.18"),
    _row(58222745, "2026-11-11 02:57:30.9", f"{V5}, identical resubmission of kernel v8: draw 3", score="0.01"),
    _row(58109075, "2026-11-08 00:19:27.0", f"{V5}: public Budget-Fit recipe unchanged", score="0.17"),
    _row(56783164, "2026-10-02 10:00:00.0", "v1_scaffold 9c208aa2c19a: swe skill", score="0.08"),
)


def test_listing_parses_past_the_cli_warning_line():
    draws = build_ledger(HISTORY, SLOT)
    assert [d.ref for d in draws] == ["58419360", "58379290", "58222745", "58109075", "56783164"]


def test_bundle_kernel_and_draw_number_come_from_description_or_backfill():
    by_ref = {d.ref: d for d in build_ledger(HISTORY, SLOT)}
    assert (by_ref["58419360"].bundle, by_ref["58419360"].kernel, by_ref["58419360"].draw) == ("v8_temp1", 9, 7)
    assert (by_ref["58109075"].bundle_hash, by_ref["58109075"].kernel, by_ref["58109075"].draw) == ("a975adbcd250", 8, 1)
    assert (by_ref["56783164"].bundle, by_ref["56783164"].draw, by_ref["56783164"].kernel) == ("v1_scaffold", None, None)


def test_near_zero_draw_is_failed_when_the_bundles_other_draws_are_healthy():
    by_ref = {d.ref: d for d in build_ledger(HISTORY, SLOT)}
    assert by_ref["58222745"].flag == "failed"
    assert by_ref["58379290"].flag == "ok"


def test_a_bundles_only_draw_is_unrated():
    by_ref = {d.ref: d for d in build_ledger(HISTORY, SLOT)}
    assert by_ref["58419360"].flag == "unrated"
    assert by_ref["56783164"].flag == "unrated"


def test_low_draws_are_not_failed_when_the_bundle_is_low_everywhere():
    listing = _listing(
        _row(1, "2026-10-01 00:00:00.0", "v0_bad 000000000000: a", score="0.02"),
        _row(2, "2026-10-02 00:00:00.0", "v0_bad 000000000000: b", score="0.03"),
    )
    assert {d.flag for d in build_ledger(listing, SLOT)} == {"ok"}


def test_hash_that_disagrees_with_the_kernel_map_is_an_error():
    listing = _listing(_row(9, "2026-11-20 00:00:00.0", _daily("v8_temp1 ffffffffffff", 9, 11)))
    with pytest.raises(LedgerError, match="kernel v9"):
        build_ledger(listing, SLOT)


def test_listing_without_header_is_an_error():
    with pytest.raises(LedgerError, match="header"):
        build_ledger("Warning: nothing here\n", SLOT)


def test_ledger_round_trips_through_csv(tmp_path):
    draws = build_ledger(HISTORY, SLOT)
    path = tmp_path / "draws.csv"
    write_ledger(path, draws)
    assert read_ledger(path) == draws


def test_next_draw_follows_the_rotation_by_draw_number():
    decision = next_draw(build_ledger(HISTORY, SLOT), SLOT, today=date(2026, 11, 25))
    assert (decision.code, decision.draw, decision.kernel) == (0, 8, 8)
    assert decision.message == _daily(V5, 8, 8)
    assert "-v 8" in decision.command and "sebmontreal/g4-submission" in decision.command


def test_next_draw_waits_while_a_draw_is_pending():
    listing = _listing(_row(5, "2026-11-24 01:00:00.0", _daily(V8, 9, 9), status="PENDING", score=""))
    decision = next_draw(build_ledger(listing + HISTORY.split(HEADER)[1], SLOT), SLOT, today=date(2026, 11, 25))
    assert decision.code == 3


def test_next_draw_refuses_a_second_submission_on_the_same_utc_day():
    decision = next_draw(build_ledger(HISTORY, SLOT), SLOT, today=date(2026, 11, 16))
    assert decision.code == 4


def test_next_draw_respects_pause():
    paused = SlotConfig.from_dict({**SLOT.raw, "pause": True})
    assert next_draw(build_ledger(HISTORY, SLOT), paused, today=date(2026, 11, 25)).code == 5


def test_report_gives_mean_without_failed_draws_and_failure_rate():
    text = report(build_ledger(HISTORY, SLOT))
    v5_line = next(line for line in text.splitlines() if line.startswith("v5_budgetfit"))
    assert "n=3" in v5_line and "mean=0.175" in v5_line and "failed=1/3" in v5_line


def test_report_ranks_final_pick_candidates_by_score_then_earlier_date():
    text = report(build_ledger(HISTORY, SLOT))
    picks = text.split("Final pick candidates")[1].splitlines()[1:4]
    assert "58379290" in picks[0]  # 0.18
    assert "58109075" in picks[1]  # 0.17, 11-08, earlier than 58419360
    assert "58419360" in picks[2]
    assert "58222745" not in text.split("Final pick candidates")[1]


def test_cli_sync_report_next_round_trip(tmp_path, capsys):
    from g4agent.cli import main

    listing, slot, ledger = tmp_path / "listing.csv", tmp_path / "slot.yaml", tmp_path / "draws.csv"
    listing.write_text(HISTORY, encoding="utf-8")
    import yaml

    slot.write_text(yaml.safe_dump(SLOT.raw), encoding="utf-8")
    common = ["--slot", str(slot), "--ledger", str(ledger)]
    assert main(["draws", "sync", "--listing", str(listing), *common]) == 0
    assert main(["draws", "report", *common]) == 0
    assert main(["draws", "next", "--today", "2026-11-25", "--shell", *common]) == 0
    out = capsys.readouterr().out
    assert "DRAW=8" in out and "KERNEL_VERSION=8" in out and "MESSAGE='v5_budgetfit a975adbcd250, kernel v8, daily draw 8," in out
    assert main(["draws", "next", "--today", "2026-11-16", *common]) == 4


def test_cli_reports_a_bad_listing_instead_of_crashing(tmp_path, capsys):
    from g4agent.cli import main

    bad = tmp_path / "bad.csv"
    bad.write_text("Warning only\n", encoding="utf-8")
    assert main(["draws", "sync", "--listing", str(bad), "--ledger", str(tmp_path / "d.csv")]) == 1
    assert "header" in capsys.readouterr().err


def test_unknown_status_counts_as_pending_so_next_fails_closed():
    listing = _listing(_row(6, "2026-11-24 01:00:00.0", _daily(V8, 9, 9), status="RUNNING", score=""))
    ledger = build_ledger(listing + HISTORY.split(HEADER)[1], SLOT)
    assert ledger[0].status == "pending"
    assert next_draw(ledger, SLOT, today=date(2026, 11, 25)).code == 3


def test_sync_refuses_a_listing_that_drops_known_submissions():
    from g4agent.draws import check_listing_covers

    old = build_ledger(HISTORY, SLOT)
    shorter = build_ledger(_listing(_row(58419360, "2026-11-16 06:23:40.4", _daily(V8, 9, 7))), SLOT)
    with pytest.raises(LedgerError, match="drops 4"):
        check_listing_covers(old, shorter)
    with pytest.raises(LedgerError, match="no submissions"):
        check_listing_covers(old, [])
    check_listing_covers(old, old)
    check_listing_covers([], shorter)


def test_a_full_page_listing_is_an_error_because_it_may_be_truncated():
    rows = "".join(_row(i, "2026-10-01 00:00:00.0", f"v0_x 00000000000{i % 10}: r") for i in range(200))
    with pytest.raises(LedgerError, match="200"):
        build_ledger(_listing(rows), SLOT)


def test_cli_shell_output_carries_competition_and_kernel(tmp_path, capsys):
    import yaml

    from g4agent.cli import main

    listing, slot, ledger = tmp_path / "l.csv", tmp_path / "s.yaml", tmp_path / "d.csv"
    listing.write_text(HISTORY, encoding="utf-8")
    slot.write_text(yaml.safe_dump(SLOT.raw), encoding="utf-8")
    common = ["--slot", str(slot), "--ledger", str(ledger)]
    main(["draws", "sync", "--listing", str(listing), *common])
    capsys.readouterr()
    main(["draws", "next", "--today", "2026-11-25", "--shell", *common])
    out = capsys.readouterr().out
    assert "COMPETITION=gemma-4-developer-agent" in out and "KERNEL=sebmontreal/g4-submission" in out
    import re

    assert all(re.match(r"^(DRAW|KERNEL_VERSION|MESSAGE|REASON|COMPETITION|KERNEL)=", line) for line in out.splitlines())


def test_next_refuses_an_empty_ledger():
    with pytest.raises(LedgerError, match="empty"):
        next_draw([], SLOT, today=date(2026, 11, 25))


def test_status_is_read_case_insensitively():
    listing = _listing(_row(7, "2026-11-20 00:00:00.0", "v0_x 000000000000: a").replace("SubmissionStatus.COMPLETE", "complete"))
    assert build_ledger(listing, SLOT)[0].status == "complete"
