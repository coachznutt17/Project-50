import json
import time
import urllib.request
import os
from datetime import datetime, timezone

ASSETS = ["BTC", "ETH", "SOL"]
FEE = 0.006
SLIP = 0.001
PATH = "paper_state.json"

def prices(asset):
    url = f"https://api.exchange.coinbase.com/products/{asset}-USD/candles?granularity=300"
    req = urllib.request.Request(
        url, headers={"User-Agent": "Project50/1.0"}
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        rows = json.load(r)
    return [
        float(r[4]) for r in sorted(rows)
        if r[0] + 300 <= time.time()
    ]

def step(s):
    p = {a: prices(a) for a in ASSETS}
    now = {a: v[-1] for a, v in p.items()}

    def equity():
        return s["cash"] + sum(
            v["qty"] * now[a] * (1-SLIP) * (1-FEE)
            for a, v in s["positions"].items()
        )

    s["peak"] = max(s["peak"], equity())
    s["halted"] = s["halted"] or equity() <= 0.8 * s["peak"]

    def log(a, side, amount, reason):
        s["trades"].append({
            "time": datetime.now(timezone.utc).isoformat(),
            "asset": a,
            "side": side,
            "amount": round(amount, 4),
            "reason": reason
        })

    sold = set()

    for a, v in list(s["positions"].items()):
        change = now[a] / v["entry"] - 1
        if s["halted"] or change <= -0.03 or change >= 0.06:
            proceeds = v["qty"] * now[a] * (1-SLIP) * (1-FEE)
            s["cash"] += proceeds
            del s["positions"][a]
            sold.add(a)
            reason = "drawdown" if s["halted"] else (
                "stop" if change <= -0.03 else "target"
            )
            log(a, "SELL", proceeds, reason)

    if not s["halted"]:
        for a, v in p.items():
            if len(v) < 50 or a in s["positions"] or a in sold:
                continue
            spend = min(15, s["cash"], equity() * 0.3)
            if spend < 5:
                continue
            fast = sum(v[-10:]) / 10
            slow = sum(v[-40:]) / 40
            if fast > slow and v[-1] > max(v[-21:-1]):
                entry = now[a] * (1+SLIP)
                s["positions"][a] = {
                    "qty": spend * (1-FEE) / entry,
                    "entry": entry
                }
                s["cash"] -= spend
                log(a, "BUY", spend, "trend breakout")

    s["equity"] = round(equity(), 4)
    s["profit"] = round(s["equity"] - 50, 4)
    s["return_pct"] = round(s["profit"] / 50 * 100, 2)
    s["updated"] = datetime.now(timezone.utc).isoformat()
    s["market_prices"] = now

    with open(PATH + ".tmp", "w") as f:
        json.dump(s, f, indent=2)
    os.replace(PATH + ".tmp", PATH)

    print("Portfolio:", s["equity"])
    print("Profit/Loss:", s["profit"])
    print("Return:", s["return_pct"], "%")
    print("Cash:", round(s["cash"], 2))
    print("Positions:", s["positions"])

if __name__ == "__main__":
    if os.path.exists(PATH):
        with open(PATH) as f:
            s = json.load(f)
    else:
        s = {
            "cash": 50.0,
            "positions": {},
            "peak": 50.0,
            "halted": False,
            "trades": []
        }
    step(s)
