"""Opt-in, bounded Helius evidence collection. All captures stay in ignored local-data."""

import argparse
import json
import logging
import os
import re
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]
HTTP_BASE = "https://mainnet.helius-rpc.com"
WS_URL = "wss://beta.helius-rpc.com/"


class ProbeError(Exception):
    """Only bounded, non-sensitive error codes may be printed."""


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ProbeError("redirect_refused")


def load_inputs(root=ROOT):
    values = {}
    if (root / ".env").exists():
        for line in (root / ".env").read_text().splitlines():
            name, separator, value = line.strip().partition("=")
            if separator and name == "HELIUS_API_KEY":
                values[name] = value.strip().strip("\"'")
    key = os.environ.get("HELIUS_API_KEY", values.get("HELIUS_API_KEY", "")).strip()
    if not key:
        raise ProbeError("missing_HELIUS_API_KEY")
    wallets = json.loads((root / "watchlist.local.json").read_text())
    if not isinstance(wallets, list) or not 1 <= len(wallets) <= 3:
        raise ProbeError("watchlist_requires_1_to_3_addresses")
    if any(
        not isinstance(w, str) or not re.fullmatch(r"[1-9A-HJ-NP-Za-km-z]{32,44}", w)
        for w in wallets
    ) or len(set(wallets)) != len(wallets):
        raise ProbeError("invalid_or_duplicate_wallet")
    return key, wallets


def private_write(path, value):
    """Do not overwrite evidence or follow an existing file symlink."""
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as output:
        json.dump(value, output, indent=2)
        output.write("\n")


class Probe:
    def __init__(self, key, directory, max_credits=500):
        self.key = key
        self.directory = directory
        self.max_credits = max_credits
        self.estimated_credits = 0
        self.calls = 0
        self.live_count = 0
        self.last_request = 0.0
        self.opener = build_opener(NoRedirect())

    def charge(self, credits):
        if self.estimated_credits + credits > self.max_credits:
            raise ProbeError("client_credit_budget_reached")
        self.estimated_credits += credits

    def post(self, path, body, credits):
        self.charge(credits)
        time.sleep(max(0, 0.6 - (time.monotonic() - self.last_request)))
        self.last_request = time.monotonic()
        self.calls += 1
        request = Request(
            HTTP_BASE + path + "?" + urlencode({"api-key": self.key}),
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            with self.opener.open(request, timeout=30) as response:
                raw = response.read(32 * 1024 * 1024 + 1)
                if len(raw) > 32 * 1024 * 1024:
                    raise ProbeError("response_size_limit")
                result = json.loads(raw)
        except HTTPError as error:
            raise ProbeError(f"http_{error.code}") from None
        except (URLError, TimeoutError, OSError):
            raise ProbeError("http_transport_error") from None
        except ValueError:
            raise ProbeError("invalid_json_response") from None
        if isinstance(result, dict) and "error" in result:
            code = result["error"].get("code")
            raise ProbeError(f"rpc_{code}" if type(code) is int else "rpc_error")
        private_write(
            self.directory / f"http-{self.calls:03d}.json",
            {
                "captured_at": datetime.now(UTC).isoformat(),
                "endpoint": path or "/",
                "request": body,
                "response": result,
            },
        )
        return result

    def rpc(self, method, params):
        # Deliberately no transaction submission or mutation methods.
        if method not in {"getSlot", "getBlockTime", "getSignaturesForAddress", "getTransaction"}:
            raise ProbeError("rpc_method_not_allowed")
        result = self.post(
            "", {"jsonrpc": "2.0", "id": self.calls + 1, "method": method, "params": params}, 1
        )
        if not isinstance(result, dict) or "result" not in result:
            raise ProbeError("unexpected_rpc_shape")
        return result["result"]

    def history(self, wallet, *, lower=None, upper=None, pages=2):
        body = {
            "address": wallet,
            "limit": 100,
            "sortOrder": "desc",
            "commitment": "confirmed",
            "includeRawTransaction": True,
        }
        if lower is not None:
            body["slot"] = {"gte": lower, "lte": upper}
        seen = set()
        rows = []
        for _ in range(pages):
            result = self.post("/v1/parsed-events/transaction-history", body, 10)
            if not isinstance(result, dict) or not isinstance(result.get("data"), list):
                raise ProbeError("unexpected_history_shape")
            rows.extend(result["data"])
            token = result.get("paginationToken")
            if not token:
                return rows, True
            if token in seen:
                raise ProbeError("repeated_history_cursor")
            seen.add(token)
            body = {**body, "paginationToken": token}
        return rows, False

    def stream(self, wallets, seconds, max_events, phase):
        from websockets.exceptions import InvalidStatus, WebSocketException
        from websockets.sync.client import connect

        # Handshake debug logging can contain the API key. Never enable it here.
        logger = logging.getLogger("wallet_observer.qualification.websocket")
        logger.disabled = True
        records = []
        started = time.monotonic()
        try:
            with connect(
                WS_URL,
                additional_headers={"x-api-key": self.key},
                open_timeout=15,
                close_timeout=2,
                max_size=8 * 1024 * 1024,
                max_queue=4,
                logger=logger,
            ) as ws:
                ws.send(
                    json.dumps(
                        {
                            "jsonrpc": "2.0",
                            "id": 1,
                            "method": "parsedTransactionSubscribe",
                            "params": [
                                {
                                    "accounts": {"include": wallets},
                                    "includeFailed": True,
                                    "includeCpi": True,
                                },
                                {"commitment": "confirmed", "details": "full"},
                            ],
                        }
                    )
                )
                ack = json.loads(ws.recv(timeout=15))
                if "error" in ack:
                    code = ack["error"].get("code")
                    raise ProbeError(
                        f"subscribe_{code}" if type(code) is int else "subscribe_error"
                    )
                if type(ack.get("result")) is not int:
                    raise ProbeError("unexpected_subscription_ack")
                subscription = ack["result"]
                private_write(self.directory / f"stream-{phase}-ack.json", ack)
                deadline = time.monotonic() + seconds
                while self.live_count < max_events and self.estimated_credits < self.max_credits:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        break
                    try:
                        raw = ws.recv(timeout=min(remaining, 5))
                    except TimeoutError:
                        continue
                    received = time.time()
                    payload = json.loads(raw)
                    if payload.get("method") != "parsedTransactionNotification":
                        raise ProbeError("unexpected_stream_message")
                    if payload["params"]["subscription"] != subscription:
                        raise ProbeError("unexpected_subscription_id")
                    self.charge(1)
                    self.live_count += 1
                    record = {"received_at_unix": received, "phase": phase, "payload": payload}
                    private_write(self.directory / f"stream-{self.live_count:04d}.json", record)
                    records.append(record)
        except InvalidStatus as error:
            raise ProbeError(f"websocket_http_{error.response.status_code}") from None
        except (WebSocketException, OSError, TimeoutError):
            raise ProbeError("websocket_transport_error") from None
        return records, round(time.monotonic() - started, 3)


def reconcile(reference, recovered, live, *, exhausted):
    """Coverage needs a nonempty independent reference and fully paginated evidence."""
    expected = set(reference)
    history = set(recovered)
    streamed = set(live)
    missing = expected - history
    return {
        "reference_count": len(expected),
        "history_count": len(history),
        "missing_from_history": len(missing),
        "history_not_streamed": len(history - streamed),
        "live_history_overlap": len(history & streamed),
        "history_exhausted": exhausted,
        "result": "pass" if expected and not missing and exhausted else "inconclusive",
    }


def run(probe, wallets, seconds, gap_seconds, max_events):
    report = {"status": "in_progress", "wallet_count": len(wallets), "history": []}
    try:
        # Historical examples can include uncommon cases without extending the live sample.
        for wallet in wallets:
            rows, exhausted = probe.history(wallet)
            report["history"].append({"rows": len(rows), "exhausted": exhausted})
        lower = probe.rpc("getSlot", [{"commitment": "confirmed"}])
        before, duration1 = probe.stream(wallets, seconds, max_events, "before")
        gap_start = probe.rpc("getSlot", [{"commitment": "confirmed"}])
        time.sleep(gap_seconds)
        gap_end = probe.rpc("getSlot", [{"commitment": "confirmed"}])
        after, duration2 = probe.stream(wallets, seconds, max_events, "after")
        upper = probe.rpc("getSlot", [{"commitment": "confirmed"}])
        report["interval"] = {
            "lower_slot": lower,
            "upper_slot": upper,
            "gap_start_slot": gap_start,
            "gap_end_slot": gap_end,
            "capture_seconds": [duration1, duration2],
            "intentional_gap_seconds": gap_seconds,
        }
        live = before + after
        live_sigs = [
            r["payload"]["params"]["result"]["value"]["transaction"]["signature"] for r in live
        ]
        report["live_notifications"] = len(live)
        report["live_duplicate_count"] = len(live_sigs) - len(set(live_sigs))
        report["recovery"] = []
        for wallet in wallets:
            rows, exhausted = probe.history(wallet, lower=max(0, lower - 32), upper=upper)
            recovered = [
                r["signature"]
                for r in rows
                if r.get("parserStatus") == "OK" and lower <= r["parsed"]["slot"] <= upper
            ]
            refs = probe.rpc(
                "getSignaturesForAddress", [wallet, {"limit": 1000, "commitment": "confirmed"}]
            )
            reference = [r["signature"] for r in refs if lower <= r["slot"] <= upper]
            gap = [r["signature"] for r in refs if gap_start <= r["slot"] <= gap_end]
            covered = len(refs) < 1000 or (bool(refs) and refs[-1]["slot"] < lower)
            result = reconcile(reference, recovered, live_sigs, exhausted=exhausted and covered)
            result["gap_reference_count"] = len(gap)
            result["gap_recovered_count"] = len(set(gap) & set(recovered))
            result["disconnect_result"] = (
                "pass"
                if set(gap) - set(live_sigs)
                and set(gap) <= set(recovered)
                and exhausted
                and covered
                else "inconclusive"
            )
            report["recovery"].append(result)
        # This is block-time-to-arrival, not a vendor-only latency or a finality measurement.
        delays = []
        block_times = {}
        for row in live:
            slot = row["payload"]["params"]["result"]["context"]["slot"]
            if slot not in block_times and len(block_times) < 20:
                block_times[slot] = probe.rpc("getBlockTime", [slot])
            if block_times.get(slot) is not None:
                delays.append(round(row["received_at_unix"] - block_times[slot], 3))
        report["block_to_arrival_seconds"] = delays
        report["status"] = "captured_requires_review"
    except ProbeError as error:
        report.update(status="blocked", error=str(error))
    except (ValueError, KeyError, TypeError, AttributeError, IndexError):
        report.update(status="blocked", error="unexpected_response_shape")
    finally:
        report.update(
            estimated_credits=probe.estimated_credits,
            http_requests=probe.calls,
            client_credit_limit=probe.max_credits,
            observed_live_count=probe.live_count,
        )
        private_write(probe.directory / "report.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Required: opt in to provider calls")
    parser.add_argument("--seconds", type=int, default=90, help="Seconds per connection (1–150)")
    parser.add_argument("--gap-seconds", type=int, default=20, help="Intentional outage (1–300)")
    parser.add_argument("--max-events", type=int, default=100, help="Total events (1–200)")
    args = parser.parse_args()
    if not args.live:
        parser.error("--live is required; this consumes Helius credits")
    if not (
        1 <= args.seconds <= 150 and 1 <= args.gap_seconds <= 300 and 1 <= args.max_events <= 200
    ):
        parser.error("probe bounds exceeded")
    try:
        key, wallets = load_inputs()
        directory = (
            ROOT / "local-data" / "qualification" / datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        )
        directory.mkdir(parents=True, mode=0o700)
        report = run(
            Probe(key, directory), wallets, args.seconds, args.gap_seconds, args.max_events
        )
        print(json.dumps(report, indent=2))
        print("Private evidence:", directory.relative_to(ROOT))
        return 0 if report["status"] != "blocked" else 2
    except (OSError, ValueError, KeyError, TypeError, AttributeError, IndexError):
        print("Probe failed: configuration or response shape invalid; private data not printed.")
        return 2
    except ProbeError as error:
        print("Probe blocked:", str(error))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
