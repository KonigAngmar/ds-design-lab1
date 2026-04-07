import httpx

FACADE_URL = "http://localhost:8000"


def run_test():
    httpx.post(f"{FACADE_URL}/metrics/reset")
    test_transactions = [
        {"user_id": "Ivan", "amount": 1000},
        {"user_id": "Ivan", "amount": -200},
        {"user_id": "Maria", "amount": 500},
        {"user_id": "Ivan", "amount": 50},
        {"user_id": "Maria", "amount": -600},
        {"user_id": "Petro", "amount": 300},
    ]

    for tx in test_transactions:
        resp = httpx.post(f"{FACADE_URL}/transaction", json=tx)
        data = resp.json()
        print(f"POST /transaction {tx} -> {data}")

    resp = httpx.get(f"{FACADE_URL}/user/Ivan")
    user_info = resp.json()
    print(f"GET /user/Ivan -> {user_info}")
    resp = httpx.get(f"{FACADE_URL}/accounts")
    all_accounts = resp.json()
    print(f"GET /accounts -> {all_accounts}")

    # Автоматична верифікація результатів
    expected_ivan = 1000 - 200 + 50
    expected_maria = 500 - 600

    actual_ivan = user_info["balance"]
    actual_maria = all_accounts.get("balances", {}).get("Maria", 0)

    print("\nРезультати верифікації")
    print(
        f"Ivan:  {actual_ivan} (Очікувалось: {expected_ivan}) -> {'ОК' if actual_ivan == expected_ivan else 'ERROR'}"
    )
    print(
        f"Maria: {actual_maria} (Очікувалось: {expected_maria}) -> {'ОК' if actual_maria == expected_maria else 'ERROR'}"
    )


if __name__ == "__main__":
    run_test()
