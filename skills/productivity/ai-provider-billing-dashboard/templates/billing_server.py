#!/usr/bin/env python3
"""
AI provider billing dashboard — stdlib-only localhost server (template).

Copy and modify. No pip installs. Binds 127.0.0.1 only — keys never reach the
browser. Run:  python billing_server.py  ->  http://localhost:8765

Provider model: auto-fetch where an API exposes balance/spend (OpenRouter),
manual top-up ledger where it does not (Anthropic — no balance API exists).
Add a provider by writing fetch_<name>(keys) and appending it in build_data().
"""
import json
import os
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# In-process cache so the dashboard refresh button doesn't re-hit rate-limited
# billing APIs (esp. Anthropic cost_report, which 429s aggressively).
_CACHE = {}
_CACHE_TTL = 300  # seconds

HERE = os.path.dirname(os.path.abspath(__file__))
PORT = 8765
CONFIG_PATH = os.path.join(HERE, "config.json")
PAYMENTS_PATH = os.path.join(HERE, "payments.json")


def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_api_keys():
    """Env vars first, then Hermes .env (config.json -> hermes_env_path)."""
    cfg = load_json(CONFIG_PATH, {})
    wanted = ["OPENROUTER_API_KEY", "ANTHROPIC_API_KEY", "ANTHROPIC_ADMIN_KEY"]
    keys = {k: os.environ[k].strip() for k in wanted if os.environ.get(k)}
    env_path = os.path.expanduser(cfg.get("hermes_env_path", "") or "")
    if env_path and os.path.exists(env_path):
        for line in open(env_path, encoding="utf-8"):
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            if k.strip() in wanted and k.strip() not in keys:
                keys[k.strip()] = v.strip().strip('"').strip("'")
    return keys


def http_get(url, headers, timeout=20):
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:
            return e.code, {"raw": str(e)}
    except Exception as e:
        return None, {"error": str(e)}


def fetch_openrouter(keys):
    key = keys.get("OPENROUTER_API_KEY")
    out = {"name": "OpenRouter", "auto": True, "ok": False, "deposited": None,
           "spent": None, "remaining": None, "note": ""}
    if not key:
        out["note"] = "No OPENROUTER_API_KEY"
        return out
    status, data = http_get("https://openrouter.ai/api/v1/credits",
                            {"Authorization": "Bearer " + key})
    if status == 200 and "data" in data:
        d = data["data"]
        dep, spent = float(d.get("total_credits", 0)), float(d.get("total_usage", 0))
        out.update(ok=True, deposited=round(dep, 2), spent=round(spent, 2),
                   remaining=round(dep - spent, 2), note="Live balance from API")
    else:
        out["note"] = f"API error: {status}"
    return out


def fetch_anthropic(keys, manual_deposits):
    """No balance API exists. Admin key gives org SPEND only via cost_report.

    THREE TRAPS this code handles (do NOT regress them):
      1. bucket_width ONLY accepts '1d' — '1month' returns HTTP 400. Bound the
         window (last ~100 days) to keep page count low.
      2. cost_report is PAGINATED (has_more/next_page) and rate-limits HARD
         (429). Loop pages, back off on 429, cache the total for _CACHE_TTL.
      3. amount is a STRING in CENTS (USD/100). Cast to float AND divide by 100.
    TWO-WALLETS MODEL: cost_report is total org usage (incl. Claude Code / Max
      subscription), NOT prepaid-API-balance drawdown. So do NOT subtract it from
      the balance. API-balance remaining = manual top-ups; expose cost_report as
      a separate 'usage_100d' reference line (what tokens would cost at API rates).
    """
    out = {"name": "Anthropic", "auto": False, "ok": False,
           "deposited": round(manual_deposits, 2), "spent": None,
           "remaining": round(manual_deposits, 2), "usage_100d": None, "note": ""}
    admin = keys.get("ANTHROPIC_ADMIN_KEY")
    if not admin:
        out["note"] = "No Admin key -> remaining = deposits. Add ANTHROPIC_ADMIN_KEY for reference usage."
        return out

    cached = _CACHE.get("anthropic_spent")
    if cached and (time.time() - cached["t"] < _CACHE_TTL):
        total = cached["v"]
        out.update(ok=True, remaining=round(manual_deposits, 2), usage_100d=round(total, 2),
                   note=f"API-balance = top-ups. Org usage 100d (ref, cached): ${round(total,2)}")
        return out

    headers = {"x-api-key": admin, "anthropic-version": "2023-06-01"}
    # bucket_width MUST be '1d'. Window = last 100 days. limit=31 packs ~31 buckets/page.
    start = (datetime.now(timezone.utc) - timedelta(days=100)).strftime("%Y-%m-%dT00:00:00Z")
    base = ("https://api.anthropic.com/v1/organizations/cost_report"
            f"?starting_at={start}&bucket_width=1d&limit=31")
    total, url, pages, last = 0.0, base, 0, None
    while url and pages < 30:
        status, data = http_get(url, headers)
        retries = 0
        while status == 429 and retries < 4:          # backoff on rate limit
            time.sleep(5 * (retries + 1))
            status, data = http_get(url, headers)
            retries += 1
        last = status
        if status != 200:
            break
        pages += 1
        for b in data.get("data", []):
            for it in b.get("results", []):
                amt = it.get("amount")
                if amt is None:
                    amt = it.get("cost", 0)
                try:
                    total += float(amt) / 100.0          # amount is STRING in CENTS
                except Exception:
                    pass
        if data.get("has_more") and data.get("next_page"):
            url = base + "&page=" + data["next_page"]
            time.sleep(1.0)
        else:
            url = None

    if last == 200:
        _CACHE["anthropic_spent"] = {"v": total, "t": time.time()}
        out.update(ok=True, remaining=round(manual_deposits, 2), usage_100d=round(total, 2),
                   note=(f"API-balance = top-ups (Anthropic has no balance API). "
                         f"Org usage 100d (reference, at API prices, mostly subscription): ${round(total,2)}"))
    elif last == 429:
        out["note"] = "Anthropic API rate-limited (429). Wait a minute and refresh. remaining = deposits."
    else:
        out["note"] = f"Admin API {last}; key must start sk-ant-admin. remaining = deposits."
    return out


def build_data():
    keys = load_api_keys()
    payments = load_json(PAYMENTS_PATH, {"payments": []}).get("payments", [])
    deposits = {}
    for p in payments:
        prov = (p.get("provider") or "").lower()
        deposits[prov] = deposits.get(prov, 0.0) + float(p.get("amount", 0))
    providers = [
        fetch_openrouter(keys),
        fetch_anthropic(keys, deposits.get("anthropic", 0.0)),
        # add more: fetch_<provider>(keys[, deposits.get("<provider>", 0.0)])
    ]
    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "providers": providers,
        "payments": sorted(payments, key=lambda x: x.get("date", ""), reverse=True),
    }


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.end_headers()
        self.wfile.write(body if isinstance(body, bytes) else body.encode("utf-8"))

    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            with open(os.path.join(HERE, "index.html"), "rb") as f:
                self._send(200, f.read(), "text/html")
        elif self.path == "/api/data":
            self._send(200, json.dumps(build_data(), ensure_ascii=False))
        else:
            self._send(404, json.dumps({"error": "not found"}))

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length).decode()
        if self.path == "/api/payment":
            try:
                p = json.loads(raw)
                assert p.get("provider") and p.get("date") and p.get("amount") is not None
                p["amount"] = float(p["amount"])
            except Exception as e:
                self._send(400, json.dumps({"error": f"bad payment: {e}"}))
                return
            data = load_json(PAYMENTS_PATH, {"payments": []})
            data.setdefault("payments", []).append(
                {"provider": p["provider"], "date": p["date"],
                 "amount": p["amount"], "note": p.get("note", "")})
            save_json(PAYMENTS_PATH, data)
            self._send(200, json.dumps({"ok": True}))
        elif self.path == "/api/payment/delete":
            try:
                idx = json.loads(raw).get("index")
                data = load_json(PAYMENTS_PATH, {"payments": []})
                shown = sorted(data["payments"], key=lambda x: x.get("date", ""), reverse=True)
                data["payments"].remove(shown[idx])
                save_json(PAYMENTS_PATH, data)
                self._send(200, json.dumps({"ok": True}))
            except Exception as e:
                self._send(400, json.dumps({"error": str(e)}))
        else:
            self._send(404, json.dumps({"error": "not found"}))


class _ReuseServer(ThreadingHTTPServer):
    allow_reuse_address = True   # smoother restarts (TIME_WAIT)


if __name__ == "__main__":
    print(f"Billing dashboard -> http://localhost:{PORT}  (Ctrl+C to stop)")
    try:
        _ReuseServer(("127.0.0.1", PORT), Handler).serve_forever()
    except OSError as e:
        # WinError 10048 = port already in use. Don't dump a traceback.
        print(f"\n!!! Port {PORT} is busy — the dashboard may already be running.")
        print(f"    Open http://localhost:{PORT}, or close the other window and relaunch.")
        print(f"    (detail: {e})")
        input("\nPress Enter to close...")
