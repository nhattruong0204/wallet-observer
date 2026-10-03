"""Synthetic control-flow tests, not provider qualification fixtures."""

import importlib.util
import json
from pathlib import Path
from urllib.error import HTTPError

import pytest

spec = importlib.util.spec_from_file_location(
    "qualify_solana", Path(__file__).resolve().parents[2] / "scripts/qualify_solana.py"
)
qualification = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qualification)


def test_credit_budget_blocks_request_before_network(tmp_path):
    probe = qualification.Probe("private-test-key", tmp_path, max_credits=9)
    with pytest.raises(qualification.ProbeError, match="budget_reached"):
        probe.history("synthetic-wallet")
    assert probe.calls == 0
    assert probe.estimated_credits == 0


@pytest.mark.parametrize("code", [401, 429, 500])
def test_http_errors_do_not_expose_credentials_or_response(tmp_path, code):
    probe = qualification.Probe("private-test-key", tmp_path)

    class FailingOpener:
        def open(self, request, timeout):
            raise HTTPError(request.full_url, code, "sensitive body", {}, None)

    probe.opener = FailingOpener()
    with pytest.raises(qualification.ProbeError) as error:
        probe.rpc("getSlot", [])
    assert str(error.value) == f"http_{code}"
    assert list(tmp_path.iterdir()) == []


def test_history_bounds_survive_pagination(tmp_path):
    probe = qualification.Probe("private-test-key", tmp_path)
    requests = []

    def post(path, body, credits):
        requests.append(body.copy())
        return (
            {"data": [{"signature": "a"}], "paginationToken": "next"}
            if len(requests) == 1
            else {"data": [{"signature": "b"}]}
        )

    probe.post = post
    rows, exhausted = probe.history("synthetic-wallet", lower=12, upper=99)
    assert exhausted and len(rows) == 2
    assert requests[1]["paginationToken"] == "next"
    assert requests[0]["slot"] == requests[1]["slot"] == {"gte": 12, "lte": 99}


def test_history_repeated_cursor_is_a_gap(tmp_path):
    probe = qualification.Probe("private-test-key", tmp_path)
    probe.post = lambda *args: {"data": [], "paginationToken": "same"}
    with pytest.raises(qualification.ProbeError, match="repeated_history_cursor"):
        probe.history("synthetic-wallet")


def test_history_page_cap_does_not_claim_exhaustion(tmp_path):
    probe = qualification.Probe("private-test-key", tmp_path)
    probe.post = lambda *args: {"data": [], "paginationToken": "next"}
    assert probe.history("synthetic-wallet", pages=1) == ([], False)


@pytest.mark.parametrize(
    "reference,recovered,exhausted",
    [
        ([], [], True),
        (["a", "b"], ["a"], True),
        (["a"], ["a"], False),
    ],
)
def test_missing_or_unbounded_evidence_never_passes(reference, recovered, exhausted):
    result = qualification.reconcile(reference, recovered, [], exhausted=exhausted)
    assert result["result"] == "inconclusive"


def test_recovery_deduplicates_overlap_but_counts_gap_events():
    result = qualification.reconcile(["a", "b"], ["a", "a", "b"], ["a"], exhausted=True)
    assert result["result"] == "pass"
    assert result["history_count"] == 2
    assert result["live_history_overlap"] == 1
    assert result["history_not_streamed"] == 1


def test_evidence_is_private_and_never_overwritten(tmp_path):
    path = tmp_path / "evidence.json"
    qualification.private_write(path, {"exact_integer": 2**64 - 1})
    assert path.stat().st_mode & 0o777 == 0o600
    assert json.loads(path.read_text())["exact_integer"] == 2**64 - 1
    with pytest.raises(FileExistsError):
        qualification.private_write(path, {})


def test_redirect_is_refused():
    with pytest.raises(qualification.ProbeError, match="redirect_refused"):
        qualification.NoRedirect().redirect_request(None, None, 302, "", {}, "https://other.test")


def test_transaction_submission_is_forbidden(tmp_path):
    probe = qualification.Probe("private-test-key", tmp_path)
    with pytest.raises(qualification.ProbeError, match="rpc_method_not_allowed"):
        probe.rpc("sendTransaction", [])
    assert probe.calls == 0
