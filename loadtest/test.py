import asyncio
import time
import httpx

FACADE = "http://localhost:8000"
N_CLIENTS = 10
N_REQ = 10000  # Кількість запитів на одного клієнта


async def reset_system():
    """Скидання метрик на facade-service."""
    async with httpx.AsyncClient(timeout=60.0) as c:
        await c.post(f"{FACADE}/metrics/reset")


async def one_client(user_id: str, amount: int, n: int):
    async with httpx.AsyncClient(timeout=60.0) as c:
        for _ in range(n):
            try:
                r = await c.post(
                    f"{FACADE}/transaction", json={"user_id": user_id, "amount": amount}
                )
                r.raise_for_status()
            except Exception as e:
                print(f"Error for user {user_id}: {e}")
                break


async def get_json(path: str):
    async with httpx.AsyncClient(timeout=60.0) as c:
        r = await c.get(f"{FACADE}{path}")
        r.raise_for_status()
        return r.json()


async def run_scenario(name: str, coro_func):
    print(f"\n>>> Запуск сценарію: {name}")
    await reset_system()  # Скидаємо метрики перед кожним тестом

    total_requests = N_CLIENTS * N_REQ
    start_time = time.perf_counter()

    # Запускаємо 10 клієнтів паралельно
    await coro_func()

    end_time = time.perf_counter()
    total_time = end_time - start_time
    rps = total_requests / total_time

    # Отримуємо метрики внутрішнього часу від facade-service
    metrics_resp = await get_json("/metrics")
    m = metrics_resp["metrics"]["post"]

    log_avg = m.get("logging_avg_ms", 0)
    cnt_avg = m.get("counter_avg_ms", 0)

    # Визначаємо "внесок" (contribution) на основі середнього часу обробки одного запиту
    print(f"\n--- Результати для {name} ---")
    print(f"Загальна кількість запитів   : {total_requests}")
    print(f"Загальний час (сек)          : {total_time:.3f}")
    print(f"Продуктивність (RPS)         : {rps:.2f}")
    print(f"Середній внесок logging-service : {log_avg:.3f} ms/req")
    print(f"Середній внесок counter-service : {cnt_avg:.3f} ms/req")

    return total_time


async def main():
    # Сценарій 1: 10 користувачів, кожен на свій рахунок
    async def scenario_1():
        tasks = [one_client(f"user_{i}", 1, N_REQ) for i in range(N_CLIENTS)]
        await asyncio.gather(*tasks)

    await run_scenario(
        "Сценарій 1: 10 клієнтів, у кожного свій рахунок (+1 x 10k)", scenario_1
    )

    # Верифікація Сценарію 1
    accounts = await get_json("/accounts")
    balances = accounts.get("balances", {})
    passed = all(balances.get(f"user_{i}") == N_REQ for i in range(N_CLIENTS))
    print(f"ВЕРИФІКАЦІЯ 1: {'УСПІШНО' if passed else 'НЕВДАЛО'}")

    # Сценарій 2: 10 клієнтів на один спільний рахунок
    async def scenario_2():
        tasks = [one_client("shared_account", 1, N_REQ) for _ in range(N_CLIENTS)]
        await asyncio.gather(*tasks)

    await run_scenario(
        "Сценарій 2: 10 клієнтів, один спільний рахунок (+1 x 10k)", scenario_2
    )

    # Верифікація Сценарію 2
    user_data = await get_json("/user/shared_account")
    final_balance = user_data.get("balance", 0)
    expected = N_CLIENTS * N_REQ
    print(f"Баланс спільного рахунку: {final_balance} (Очікувалось: {expected})")
    print(f"ВЕРИФІКАЦІЯ 2: {'УСПІШНО' if final_balance == expected else 'НЕВДАЛО'}")


if __name__ == "__main__":
    asyncio.run(main())
