from flask import Flask, request, jsonify
import os, time, uuid, threading
import requests
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)

LOGGING_URL = os.getenv("LOGGING_URL", "http://logging-service:8000")
COUNTER_URL = os.getenv("COUNTER_URL", "http://counter-service:8000")

_metrics_lock = threading.Lock()
metrics = {
    "post": {"count": 0, "logging_total_ms": 0.0, "counter_total_ms": 0.0},
    "get_user": {"count": 0, "logging_total_ms": 0.0, "counter_total_ms": 0.0},
    "get_accounts": {"count": 0, "counter_total_ms": 0.0},
}


def _ms(dt_ns: int) -> float:
    return dt_ns / 1_000_000.0


session = requests.Session()
executor = ThreadPoolExecutor(max_workers=32)


def _timed(method: str, url: str, **kwargs):
    t0 = time.perf_counter_ns()
    resp = session.request(method, url, timeout=10, **kwargs)
    dt = time.perf_counter_ns() - t0
    return resp, dt


@app.post("/transaction")
def create_transaction():
    data = request.get_json(force=True)
    user_id = str(data["user_id"])
    amount = int(data["amount"])

    transaction_id = str(uuid.uuid4())
    timestamp = time.time_ns()
    full_tx = {
        "transaction_id": transaction_id,
        "user_id": user_id,
        "amount": amount,
        "timestamp": timestamp,
    }

    f_log = executor.submit(_timed, "POST", f"{LOGGING_URL}/transaction", json=full_tx)
    f_cnt = executor.submit(_timed, "POST", f"{COUNTER_URL}/transaction", json=full_tx)

    (log_resp, log_dt) = f_log.result()
    (cnt_resp, cnt_dt) = f_cnt.result()

    print(
        f"[FACADE] TX {transaction_id[:8]}: log {log_resp.status_code} ({_ms(log_dt):.2f}ms), cnt {cnt_resp.status_code} ({_ms(cnt_dt):.2f}ms)"
    )

    if log_resp.status_code >= 400:
        return (
            jsonify({"error": "logging-service error", "details": log_resp.text}),
            502,
        )
    if cnt_resp.status_code >= 400:
        return (
            jsonify({"error": "counter-service error", "details": cnt_resp.text}),
            502,
        )

    balance = cnt_resp.json().get("balance", 0)

    with _metrics_lock:
        metrics["post"]["count"] += 1
        metrics["post"]["logging_total_ms"] += _ms(log_dt)
        metrics["post"]["counter_total_ms"] += _ms(cnt_dt)

    return jsonify({"transaction_id": transaction_id, "balance": balance})


@app.get("/user/<user_id>")
def get_user(user_id: str):
    f_log = executor.submit(_timed, "GET", f"{LOGGING_URL}/transactions/{user_id}")
    f_cnt = executor.submit(_timed, "GET", f"{COUNTER_URL}/balance/{user_id}")

    (log_resp, log_dt) = f_log.result()
    (cnt_resp, cnt_dt) = f_cnt.result()

    if log_resp.status_code >= 400:
        return (
            jsonify({"error": "logging-service error", "details": log_resp.text}),
            502,
        )
    if cnt_resp.status_code >= 400:
        return (
            jsonify({"error": "counter-service error", "details": cnt_resp.text}),
            502,
        )

    with _metrics_lock:
        metrics["get_user"]["count"] += 1
        metrics["get_user"]["logging_total_ms"] += _ms(log_dt)
        metrics["get_user"]["counter_total_ms"] += _ms(cnt_dt)

    return jsonify(
        {
            "balance": cnt_resp.json().get("balance", 0),
            "transactions": log_resp.json().get("transactions", []),
        }
    )


@app.get("/accounts")
def get_accounts():
    resp, dt = _timed("GET", f"{COUNTER_URL}/balances")
    if resp.status_code >= 400:
        return jsonify({"error": "counter-service error", "details": resp.text}), 502

    with _metrics_lock:
        metrics["get_accounts"]["count"] += 1
        metrics["get_accounts"]["counter_total_ms"] += _ms(dt)

    return jsonify(resp.json())


@app.get("/metrics")
def get_metrics():
    with _metrics_lock:
        out = {"ts": time.time(), "metrics": {k: v.copy() for k, v in metrics.items()}}

    for k, v in out["metrics"].items():
        c = v.get("count", 0) or 0
        if c > 0:
            if "logging_total_ms" in v:
                v["logging_avg_ms"] = v["logging_total_ms"] / c
            if "counter_total_ms" in v:
                v["counter_avg_ms"] = v["counter_total_ms"] / c
    return jsonify(out)


@app.post("/metrics/reset")
def reset_metrics():
    # 1. Reset metrics
    with _metrics_lock:
        metrics["post"] = {"count": 0, "logging_total_ms": 0.0, "counter_total_ms": 0.0}
        metrics["get_user"] = {
            "count": 0,
            "logging_total_ms": 0.0,
            "counter_total_ms": 0.0,
        }
        metrics["get_accounts"] = {"count": 0, "counter_total_ms": 0.0}

    # 2. Reset other services
    try:
        session.post(f"{LOGGING_URL}/reset")
        session.post(f"{COUNTER_URL}/reset")
    except Exception as e:
        print(f"Error resetting services: {e}")

    return jsonify({"ok": True})
