"""Generate multi-day test logs from 3 nodes with cross-machine trace chains.

向本地 ikc-log-center 镜像（默认 http://127.0.0.1:9315）灌入模拟测试数据：
  - 3 个不同 IP 节点（node-A / node-B / node-C），各跑不同微服务
  - 默认最近 10 天（可按 DAYS 配置），每天默认 5000 条（可按 DAILY_LOGS 配置）
  - 跨节点 trace chain：模拟 gateway -> user -> order -> payment -> notification 的分布式调用

用法：
  LOG_CENTER_URL=http://127.0.0.1:9315 DAYS=10 DAILY_LOGS=5000 \
      /home/ikc-log-center/.venv/bin/python scripts/gen_log_center_test_data.py
"""
from __future__ import annotations

import os
import random
import uuid
from datetime import datetime, timedelta

import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SERVER_URL = os.getenv("LOG_CENTER_URL", "http://127.0.0.1:9315")
DAYS = int(os.getenv("DAYS", "10"))
DAILY_LOGS = int(os.getenv("DAILY_LOGS", "5000"))
BATCH_SIZE = 100

# Time range: recent N days, ending at now (per-day data evenly distributed)
TIME_END = datetime.now().replace(microsecond=0)
TIME_START = TIME_END - timedelta(days=DAYS)

# ---------------------------------------------------------------------------
# Machine definitions: 3 nodes
# ---------------------------------------------------------------------------
MACHINES = {
    "192.168.1.15": {
        "hostname": "node-A",
        "services": ["gateway", "user-service"],
    },
    "192.168.23.10": {
        "hostname": "node-B",
        "services": ["order-service", "payment-service"],
    },
    "172.16.8.20": {
        "hostname": "node-C",
        "services": ["inventory-service", "notification-service"],
    },
}

# ---------------------------------------------------------------------------
# Service message templates
# ---------------------------------------------------------------------------
SERVICE_MSGS = {
    "gateway": [
        ("INFO", "Request received: {method} {path} from client {client_ip}"),
        ("INFO", "Routing to upstream: {target_service} @ {target_host}"),
        ("WARNING", "Upstream response slow: {latency}ms from {target_host}"),
        ("INFO", "Response sent: {status_code} in {latency}ms"),
        ("ERROR", "Upstream timeout after {timeout}ms: {target_service} @ {target_host}"),
        ("ERROR", "Connection reset by peer: {target_host}:{target_port}"),
    ],
    "user-service": [
        ("INFO", "User authentication: user_id={user_id}, source_ip={client_ip}"),
        ("INFO", "Token validated, forwarding to {target_host}"),
        ("WARNING", "Login attempt from unusual IP: {client_ip}"),
        ("ERROR", "Authentication failed: invalid credentials for user {user_id}"),
        ("INFO", "User profile loaded: {user_id}, calling order-service @ {target_host}"),
        ("DEBUG", "Session cache hit for user {user_id}"),
    ],
    "order-service": [
        ("INFO", "Order created: order_id={order_id}, amount={amount}, caller={caller_host}"),
        ("INFO", "Inventory check passed: sku={sku}"),
        ("WARNING", "Low inventory for sku={sku}, remaining={stock}"),
        ("ERROR", "Order validation failed: {reason}"),
        ("INFO", "Order {order_id} → {status}, notifying payment @ {target_host}"),
        ("INFO", "Order persisted to database, latency={latency}ms"),
    ],
    "payment-service": [
        ("INFO", "Payment initiated: order_id={order_id}, amount={amount}, caller={caller_host}"),
        ("INFO", "Payment gateway response: {gateway_status}"),
        ("WARNING", "Payment retry attempt {retry}/3 for order {order_id}"),
        ("ERROR", "Payment declined: {reason}"),
        ("INFO", "Payment completed: txn_id={txn_id}"),
        ("CRITICAL", "Payment gateway unreachable after {timeout}ms"),
    ],
    "inventory-service": [
        ("INFO", "Inventory updated: sku={sku}, delta={stock}, caller={caller_host}"),
        ("INFO", "Stock query: sku={sku}, remaining={stock}"),
        ("WARNING", "Stock below threshold: sku={sku}, remaining={stock}"),
        ("ERROR", "Inventory sync failed: {reason}"),
        ("INFO", "Inventory reserved for order {order_id}"),
    ],
    "notification-service": [
        ("INFO", "Notification queued: type={notify_type}, target={notify_target}, caller={caller_host}"),
        ("INFO", "Email sent to {notify_target}"),
        ("WARNING", "SMS delivery delayed: carrier timeout"),
        ("ERROR", "Push notification failed: device not registered"),
        ("INFO", "Notification delivered: type={notify_type}"),
    ],
}

METHODS = ["GET", "POST", "PUT", "DELETE", "PATCH"]
PATHS = ["/api/orders", "/api/users/profile", "/api/payments", "/api/products", "/api/cart", "/api/inventory"]
STATUSES = [200, 200, 200, 201, 204, 400, 404, 500, 502]
GATEWAYS = ["alipay", "wechat_pay", "unionpay", "stripe"]
NOTIFY_TYPES = ["email", "sms", "push", "webhook"]
REASONS = ["insufficient balance", "card expired", "network timeout", "invalid parameter", "duplicate request", "fraud detected"]
SKUS = ["SKU-1001", "SKU-2002", "SKU-3003", "SKU-4004", "SKU-5005"]
ORDER_STATUSES = ["pending", "confirmed", "shipped", "completed", "cancelled"]
CLIENT_IPS = [f"10.0.{random.randint(1, 10)}.{random.randint(1, 254)}" for _ in range(20)]


def fill_template(msg: str, machine_ip: str, target_ip: str) -> str:
    replacements = {
        "{method}": random.choice(METHODS),
        "{path}": random.choice(PATHS),
        "{target_service}": random.choice(["user-service", "order-service", "payment-service", "inventory-service"]),
        "{target_host}": target_ip,
        "{target_port}": str(random.choice([8080, 8443, 9090])),
        "{caller_host}": machine_ip,
        "{client_ip}": random.choice(CLIENT_IPS),
        "{latency}": str(random.randint(5, 3000)),
        "{timeout}": str(random.choice([3000, 5000, 10000])),
        "{status_code}": str(random.choice(STATUSES)),
        "{user_id}": f"U{random.randint(10000, 99999)}",
        "{order_id}": f"ORD-{random.randint(100000, 999999)}",
        "{amount}": f"¥{random.uniform(10, 5000):.2f}",
        "{sku}": random.choice(SKUS),
        "{stock}": str(random.randint(1, 20)),
        "{reason}": random.choice(REASONS),
        "{status}": random.choice(ORDER_STATUSES),
        "{gateway_status}": random.choice(["SUCCESS", "SUCCESS", "PENDING", "FAILED"]),
        "{retry}": str(random.randint(1, 3)),
        "{txn_id}": f"TXN-{uuid.uuid4().hex[:12].upper()}",
        "{notify_type}": random.choice(NOTIFY_TYPES),
        "{notify_target}": f"user{random.randint(1000, 9999)}@example.com",
    }
    for k, v in replacements.items():
        msg = msg.replace(k, v)
    return msg


def generate_cross_machine_chain(day_start: datetime, day_end: datetime) -> list[dict]:
    """Generate a trace chain that crosses all 3 nodes within the given day window."""
    trace_id = f"trace-{uuid.uuid4().hex[:12]}"
    root_span = f"span-{uuid.uuid4().hex[:8]}"
    window_seconds = max(1, int((day_end - day_start).total_seconds()))

    ips = list(MACHINES.keys())
    ip_a, ip_b, ip_c = ips[0], ips[1], ips[2]

    # Every chain visits all 3 nodes: pick 1-2 services per node
    chain = []
    for node_ip in (ip_a, ip_b, ip_c):
        for svc in random.sample(MACHINES[node_ip]["services"], k=random.randint(1, 2)):
            chain.append((node_ip, svc))

    chain_base = day_start + timedelta(seconds=random.randint(0, window_seconds - 30))
    entries = []
    span_seq = 0
    last_span = root_span

    for node_ip, svc in chain:
        for _ in range(random.randint(1, 2)):
            level, template = random.choice(SERVICE_MSGS[svc])
            # 目标节点从其余两个节点中随机选，模拟跨节点调用
            target_ip = random.choice([ip for ip in ips if ip != node_ip])
            msg = fill_template(template, node_ip, target_ip)
            span_id = f"span-{uuid.uuid4().hex[:8]}"
            ts = chain_base + timedelta(milliseconds=span_seq * random.randint(20, 80))
            entries.append({
                "ts": ts.strftime("%Y-%m-%dT%H:%M:%S"),
                "level": level,
                "logger": svc,
                "message": msg,
                "trace_id": trace_id,
                "span_id": span_id,
                "parent_id": last_span,
                "service": svc,
                "source_ip": node_ip,
                "hostname": MACHINES[node_ip]["hostname"],
            })
            last_span = span_id
            span_seq += 1

    return entries


def main() -> None:
    total_target = DAYS * DAILY_LOGS
    print(f"Target: {total_target} logs ({DAILY_LOGS}/day × {DAYS} days) from 3 nodes")
    for ip, info in MACHINES.items():
        print(f"  {ip} ({info['hostname']}) — {', '.join(info['services'])}")
    print(f"Time range: {TIME_START.strftime('%Y-%m-%d %H:%M')} ~ {TIME_END.strftime('%Y-%m-%d %H:%M')}")
    print(f"Server: {SERVER_URL}")
    print()

    all_entries: list[dict] = []
    chain_count = 0

    for day in range(DAYS):
        day_start = TIME_START + timedelta(days=day)
        day_end = day_start + timedelta(days=1)
        while True:
            chain = generate_cross_machine_chain(day_start, day_end)
            day_entries = [e for e in chain if day_start <= datetime.fromisoformat(e["ts"]) < day_end]
            all_entries.extend(day_entries)
            chain_count += 1
            if len([e for e in all_entries if day_start <= datetime.fromisoformat(e["ts"]) < day_end]) >= DAILY_LOGS:
                break

    all_entries = all_entries[:total_target]
    all_entries.sort(key=lambda e: e["ts"])

    print(f"Generated {len(all_entries)} entries across {chain_count} cross-node traces")
    for ip, info in MACHINES.items():
        count = sum(1 for e in all_entries if e["source_ip"] == ip)
        print(f"  {ip} ({info['hostname']}): {count} entries")
    print(f"Sending in batches of {BATCH_SIZE}...")

    sent = 0
    for i in range(0, len(all_entries), BATCH_SIZE):
        batch = all_entries[i:i + BATCH_SIZE]
        try:
            resp = requests.post(f"{SERVER_URL}/ingest", json=batch, timeout=15)
            if resp.status_code == 200 and resp.json().get("status") == "ok":
                sent += len(batch)
                if sent % 5000 == 0 or sent == len(all_entries):
                    print(f"  Sent {sent}/{len(all_entries)}")
            else:
                print(f"  ERROR: HTTP {resp.status_code} - {resp.text[:100]}")
                break
        except Exception as exc:
            print(f"  ERROR: {exc}")
            break

    print(f"\nDone! Total stored: {sent} logs from 3 nodes over {DAYS} days")


if __name__ == "__main__":
    main()
