import time
import random
import requests
import pandas as pd
from datetime import datetime, timedelta, timezone

BASE_URL = "https://api.binance.com"
KLINES_EP = "/api/v3/klines"
EXINFO_EP = "/api/v3/exchangeInfo"

#asset
SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "XRPUSDT", "SOLUSDT"]
INTERVAL = "1h"

TEST_DAYS = 730       #2 anni
LIMIT = 1000
SLEEP_OK = 0.25
MAX_RETRIES = 8
SAVE_CSV = True

session = requests.Session()
session.headers.update({"User-Agent": "DM-Project-Binance/1.0 (requests)"})

def ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)

def dt_from_ms(x: int) -> datetime:
    return datetime.fromtimestamp(x / 1000, tz=timezone.utc)

def robust_sleep(sec: float):
    time.sleep(max(0.0, sec + random.uniform(-0.10, 0.20)))

def request_json(url: str, params=None, timeout=30):
    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = session.get(url, params=params, timeout=timeout)

            if r.status_code in (429, 418):
                wait = min(60, 2 ** attempt)
                print(f"[BINANCE] {r.status_code} rate/ban | attempt={attempt} | wait~{wait}s | URL={r.url}")
                robust_sleep(wait)
                continue

            if r.status_code >= 500:
                wait = min(30, 2 * attempt)
                print(f"[BINANCE] HTTP {r.status_code} server err | attempt={attempt} | wait~{wait}s | URL={r.url}")
                robust_sleep(wait)
                continue

            # se è 400, non ha senso retry infinito: stampiamo body e stop
            if r.status_code == 400:
                print(f"[BINANCE] HTTP 400 Bad Request | URL={r.url}")
                print("Body:", r.text[:300])
                r.raise_for_status()

            r.raise_for_status()
            return r.json(), r.headers, r.url

        except Exception as e:
            last_err = e
            wait = min(20, 2 * attempt)
            print(f"[BINANCE] exception | attempt={attempt} | wait~{wait}s | err={e}")
            robust_sleep(wait)

    raise RuntimeError(f"Request failed after {MAX_RETRIES} retries: {last_err}")

def get_symbol_info(symbol: str):
    url = BASE_URL + EXINFO_EP
    j, headers, full_url = request_json(url, params={"symbol": symbol})
    syms = j.get("symbols", [])
    return syms[0] if syms else None

def fetch_klines(symbol: str, interval: str, start_ms: int, end_ms: int, limit=1000):
    url = BASE_URL + KLINES_EP
    params = {
        "symbol": symbol,
        "interval": interval,
        "startTime": start_ms,
        "endTime": end_ms,
        "limit": limit
    }
    j, headers, full_url = request_json(url, params=params)
    used_weight = None
    for k, v in headers.items():
        if k.upper().startswith("X-MBX-USED-WEIGHT"):
            used_weight = (k, v)
            break
    return j, used_weight, full_url

def first_kline_time(symbol: str, interval: str):
    j, _, _ = fetch_klines(symbol, interval, start_ms=0, end_ms=ms(datetime.now(timezone.utc)), limit=1)
    if not j:
        return None
    return int(j[0][0])

def last_kline_time(symbol: str, interval: str):
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=10)
    j, _, _ = fetch_klines(symbol, interval, start_ms=ms(start), end_ms=ms(now), limit=1000)
    if not j:
        return None
    return int(j[-1][0])

def download_range(symbol: str, interval: str, start_dt: datetime, end_dt: datetime):
    start_ms = ms(start_dt)
    end_ms = ms(end_dt)

    all_rows = []
    cur = start_ms
    n_calls = 0

    while True:
        chunk, used_weight, url = fetch_klines(symbol, interval, cur, end_ms, limit=LIMIT)
        n_calls += 1

        if not chunk:
            break

        all_rows.extend(chunk)
        last_open = int(chunk[-1][0])
        cur = last_open + 1

        if len(chunk) < LIMIT:
            break

        robust_sleep(SLEEP_OK)

    cols = [
        "open_time_ms", "open", "high", "low", "close", "volume",
        "close_time_ms", "quote_asset_volume", "n_trades",
        "taker_buy_base_vol", "taker_buy_quote_vol", "ignore"
    ]
    df = pd.DataFrame(all_rows, columns=cols)
    if df.empty:
        return df, n_calls

    df["symbol"] = symbol
    df["open_time"] = pd.to_datetime(df["open_time_ms"], unit="ms", utc=True)
    df["close_time"] = pd.to_datetime(df["close_time_ms"], unit="ms", utc=True)

    for c in ["open", "high", "low", "close", "volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    df = df.sort_values("open_time").drop_duplicates(subset=["symbol", "open_time_ms"]).reset_index(drop=True)
    return df, n_calls

def dq_klines_hourly(df: pd.DataFrame, start_dt: datetime, end_dt: datetime):
    if df.empty:
        return {"status": "empty"}

    s = start_dt.replace(minute=0, second=0, microsecond=0, tzinfo=timezone.utc)
    e = end_dt.replace(minute=0, second=0, microsecond=0, tzinfo=timezone.utc)
    expected = pd.date_range(start=s, end=e - timedelta(hours=1), freq="H", tz="UTC")

    present = df["open_time"].dt.floor("h")
    present_idx = pd.Index(present.unique())
    missing = pd.Index(expected).difference(present_idx)

    bad_price = int(((df["open"] <= 0) | (df["high"] <= 0) | (df["low"] <= 0) | (df["close"] <= 0)).sum())
    bad_hl = int((df["high"] < df["low"]).sum())
    bad_vol = int((df["volume"] < 0).sum())

    return {
        "rows": int(len(df)),
        "expected_hours": int(len(expected)),
        "present_hours": int(len(present_idx)),
        "missing_hours": int(len(missing)),
        "coverage": float(len(present_idx) / len(expected)) if len(expected) else None,
        "bad_price_rows": bad_price,
        "bad_high_lt_low_rows": bad_hl,
        "bad_negative_volume_rows": bad_vol,
        "missing_examples_first10": [str(x) for x in missing[:10]]
    }

def main():
    print("=== BINANCE TEST START ===")

    # 1) exchangeInfo per symbol
    print("\n--- SYMBOL CHECK (exchangeInfo) ---")
    sym_info = {}
    for sym in SYMBOLS:
        info = get_symbol_info(sym)
        if not info:
            print(f"{sym}: NON trovato in exchangeInfo")
        else:
            sym_info[sym] = info
            print(f"{sym}: status={info.get('status')} base={info.get('baseAsset')} quote={info.get('quoteAsset')}")
        robust_sleep(0.2)

    # 2) prima/ultima candela disponibili
    print("\n--- FIRST/LAST KLINE (1h) ---")
    for sym in SYMBOLS:
        ft = first_kline_time(sym, INTERVAL)
        lt = last_kline_time(sym, INTERVAL)
        print(f"{sym}: first={dt_from_ms(ft) if ft else None} | last~={dt_from_ms(lt) if lt else None}")
        robust_sleep(0.2)

    # 3) download test range
    end_dt = datetime(2026, 1, 24, 0, 0, 0, tzinfo=timezone.utc)  # include tutto il 23
    start_dt = end_dt - timedelta(days=730)

    print(f"\n--- DOWNLOAD TEST RANGE: {TEST_DAYS} giorni | {start_dt} -> {end_dt} ---")
    all_dfs = []
    calls_total = 0

    for sym in SYMBOLS:
        print(f"\n### Download {sym} ###")
        df, n_calls = download_range(sym, INTERVAL, start_dt, end_dt)
        calls_total += n_calls

        dq = dq_klines_hourly(df, start_dt, end_dt)
        print("Calls:", n_calls)
        print("DQ:", dq)

        if SAVE_CSV and not df.empty:
            out_name = f"binance_{sym}_{INTERVAL}_{TEST_DAYS}d.csv"
            df.to_csv(out_name, index=False)
            print("Saved:", out_name)

        all_dfs.append(df)
        robust_sleep(0.8)

    df_all = pd.concat(all_dfs, ignore_index=True) if all_dfs else pd.DataFrame()
    if SAVE_CSV and not df_all.empty:
        df_all.to_csv(f"binance_ALL_{INTERVAL}_{TEST_DAYS}d.csv", index=False)
        print("\nSaved:", f"binance_ALL_{INTERVAL}_{TEST_DAYS}d.csv")

    print("\n=== SUMMARY ===")
    print("Total API calls:", calls_total)
    est_1y_calls = 18 * len(SYMBOLS)  # ~17520/1000 ~ 18 per asset
    print(f"Stima chiamate per 1 anno (1h): ~{est_1y_calls}")
    print("Done.")

if __name__ == "__main__":
    main()

# ====== INPUT ======
INTERVAL = "1h"
TEST_DAYS = 730
BINANCE_PATH = f"binance_ALL_{INTERVAL}_{TEST_DAYS}d.csv"

# End : 24/01 00:00 UTC = include tutto il 23 gennaio
END_DT = datetime(2026, 1, 24, 0, 0, 0, tzinfo=timezone.utc)
START_DT = END_DT - timedelta(days=TEST_DAYS)

b = pd.read_csv(BINANCE_PATH)
b["open_time"] = pd.to_datetime(b["open_time"], utc=True, errors="coerce")
b["ts_hour_utc"] = b["open_time"].dt.floor("h")

# dedup
dup_total = int(b.duplicated(["symbol", "ts_hour_utc"]).sum())
dup_by_symbol = (b.assign(is_dup=b.duplicated(["symbol", "ts_hour_utc"], keep=False))
                   .groupby("symbol")["is_dup"]
                   .sum()
                   .reset_index(name="dup_rows"))

print("Loaded:", BINANCE_PATH, "| rows:", len(b))
print("\n=== DUPLICATES (symbol, ts_hour_utc) ===")
print("dup_total:", dup_total)
print(dup_by_symbol.to_string(index=False))

# ====== COVERAGE / BUCHI ======
expected = pd.date_range(
    start=pd.to_datetime(START_DT, utc=True).floor("h"),
    end=pd.to_datetime(END_DT, utc=True).floor("h") - timedelta(hours=1),
    freq="H",
    tz="UTC"
)

rows = []
for sym, g in b.groupby("symbol"):
    g = g.drop_duplicates(["symbol", "ts_hour_utc"])
    present = pd.DatetimeIndex(g["ts_hour_utc"].dropna().unique())
    missing = expected.difference(present)

    rows.append({
        "symbol": sym,
        "expected_hours": int(len(expected)),
        "present_hours": int(len(present)),
        "missing_hours": int(len(missing)),
        "coverage": float(len(present) / len(expected)) if len(expected) else None
    })

dq_table = pd.DataFrame(rows).sort_values("symbol")

print("\n=== DQ REPORT (per symbol) ===")
print(dq_table.to_string(index=False))