from flask import Flask, request, jsonify
from dataclasses import asdict, dataclass
from typing import Dict, List
import threading

app = Flask(__name__)


@dataclass
class Transaction:
    transaction_id: str
    user_id: str
    amount: int
    timestamp: int


_lock = threading.Lock()
_by_id: Dict[str, Transaction] = {}
_by_user: Dict[str, List[Transaction]] = {}


@app.post("/transaction")
def add_transaction():
    data = request.get_json(force=True)
    tx = Transaction(
        transaction_id=str(data["transaction_id"]),
        user_id=str(data["user_id"]),
        amount=int(data["amount"]),
        timestamp=int(data["timestamp"]),
    )
    with _lock:
        _by_id[tx.transaction_id] = tx
        _by_user.setdefault(tx.user_id, []).append(tx)
    print(f"[LOG] Received transaction: {tx}")
    return jsonify({"ok": True})


@app.get("/transactions/<user_id>")
def get_user_transactions(user_id: str):
    with _lock:
        txs = _by_user.get(user_id, [])
        return jsonify({"transactions": [asdict(t) for t in txs]})


@app.get("/transactions")
def get_all_transactions():
    with _lock:
        return jsonify({"transactions": [asdict(t) for t in _by_id.values()]})


@app.post("/reset")
def reset_data():
    with _lock:
        _by_id.clear()
        _by_user.clear()
    return jsonify({"ok": True})
