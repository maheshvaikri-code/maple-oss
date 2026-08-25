"""Tests for the local MAPLE doctor CLI command."""

import json

from maple.cli import doctor_report, main


def test_doctor_report_is_local_and_ready():
    report = doctor_report()

    assert report["status"] == "SUCCESS"
    assert report["ready"] is True
    assert report["network"] is False
    assert all(report["checks"].values())


def test_doctor_json_output(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["maple", "doctor", "--json"])

    exit_code = main()
    output = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert output["status"] == "SUCCESS"
    assert output["checks"]["interop"] is True
    assert output["checks"]["server"] is True
