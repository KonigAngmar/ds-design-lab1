from flask import Flask, request, jsonify
from typing import Dict
import threading

app = Flask(__name__)

_lock = threading.Lock()
_balances: Dict[str, int] = {}


@app.post("/transaction")
def apply_transaction():
    data = request.get_json(force=True)
    user_id = str(data["user_id"])
    amount = int(data["amount"])

    with _lock:
        cur = _balances.get(user_id, 0) + amount
        _balances[user_id] = cur
        print(f"[COUNTER] User {user_id} balance: {cur} ({amount:+d})")
        return jsonify({"balance": cur})


@app.get("/balance/<user_id>")
def get_balance(user_id: str):
    with _lock:
        return jsonify({"balance": _balances.get(user_id, 0)})


@app.get("/balances")
def get_all_balances():
    with _lock:
        return jsonify({"balances": dict(_balances)})


@app.post("/reset")
def reset_data():
    with _lock:
        _balances.clear()
    return jsonify({"ok": True})
