#!/usr/bin/env python3
import time
import uuid
import requests

BASE = "http://localhost:8000"

# ----------------------
# Helper functions
# ----------------------

def check_health():
    print(">> Checking /health ...")
    r = requests.get(f"{BASE}/health")
    assert r.status_code == 200
    assert r.json().get("status") == "OK"
    print("   PASSED")


def create_order():
    print(">> Creating order /orders ...")
    payload = {
        "clientId": "SMOKE",
        "symbol": "XAUUSD",
        "side": "BUY",
        "type": "LIMIT",
        "qty": 1,
        "price": 2000.0,
        "timeInForce": "GTC",
    }
    r = requests.post(f"{BASE}/orders", json=payload)
    assert r.status_code == 201, f"Expected 201, got {r.status_code}"
    order = r.json()
    print("   Order created:", order["id"])
    return order["id"]


def get_order(order_id):
    r = requests.get(f"{BASE}/orders/{order_id}")
    assert r.status_code == 200, "Expected 200 for GET order"
    return r.json()


def wait_for_order_state_change(order_id, max_wait=3.0, interval=0.2):
    print(">> Waiting for order state to change from NEW ...")

    elapsed = 0
    while elapsed < max_wait:
        order = get_order(order_id)
        if order["status"] != "NEW":
            print(f"   Status changed to: {order['status']}")
            return order
        time.sleep(interval)
        elapsed += interval

    raise AssertionError("Order stayed in NEW state too long — FIX mock may not be running")


def list_orders():
    print(">> Listing /orders?clientId=SMOKE ...")
    r = requests.get(f"{BASE}/orders", params={"clientId": "SMOKE"})
    assert r.status_code == 200
    data = r.json()
    print(f"   Found {len(data)} orders")
    return data


def cancel_fake_order():
    print(">> Cancelling non-existing order (expect 404) ...")
    fake_id = str(uuid.uuid4())
    r = requests.post(f"{BASE}/orders/{fake_id}/cancel")
    assert r.status_code == 404, f"Expected 404, got {r.status_code}"
    print("   PASSED (404 received)")


def get_positions():
    print(">> GET /positions?clientId=SMOKE ...")
    r = requests.get(f"{BASE}/positions", params={"clientId": "SMOKE"})
    assert r.status_code == 200
    positions = r.json()
    print("   Positions:", positions)
    return positions


# ----------------------
# Smoke Test Runner
# ----------------------

def run():
    print("\n=== SMOKE TESTS START ===\n")

    check_health()

    order_id = create_order()

    # Wait for FIX mock to process fills
    order = wait_for_order_state_change(order_id)

    # Final state must be one of:
    valid_states = (
        "PENDING_SEND",
        "SENT",
        "PARTIALLY_FILLED",
        "FILLED",
        "REJECTED",
    )
    assert order["status"] in valid_states, f"Unexpected status: {order['status']}"

    list_orders()
    cancel_fake_order()
    get_positions()

    print("\n=== ALL SMOKE TESTS PASSED ===\n")


if __name__ == "__main__":
    run()
