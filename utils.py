# utils.py
import os
import io
import time
import logging
from typing import Dict, Optional, Tuple, List
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import requests
import yfinance as yf

# Optional google sheets access
try:
    import gspread
    from google.oauth2.service_account import Credentials
    GS_ENABLED = True
except Exception:
    GS_ENABLED = False

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


# ---------- Google Sheets helpers ----------

def _get_gspread_client_from_service_account_json_path(path: str):
    """
    Create a gspread client using a service-account JSON file path.
    """
    scopes = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
    creds = Credentials.from_service_account_file(path, scopes=scopes)
    return gspread.authorize(creds)


def _get_gspread_client_from_service_account_info(info_dict: dict):
    scopes = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
    creds = Credentials.from_service_account_info(info_dict, scopes=scopes)
    return gspread.authorize(creds)


def read_sheet_public_csv(sheet_csv_url: str) -> pd.DataFrame:
    """
    Read an exported CSV URL from Google Sheets (public / published).
    Example exported CSV url:
      https://docs.google.com/spreadsheets/d/<SHEET_ID>/export?format=csv&gid=<GID>
    """
    r = requests.get(sheet_csv_url, timeout=12)
    r.raise_for_status()
    return pd.read_csv(io.StringIO(r.text))


def read_sheet_private(service_account: dict, spreadsheet_id: str, worksheet_name_or_index=0) -> pd.DataFrame:
    """
    Read a sheet using service account credentials (service_account is dict parsed from JSON).
    spreadsheet_id is the ID portion in the sheet URL.
    worksheet_name_or_index: name or 0-based index.
    """
    if not GS_ENABLED:
        raise RuntimeError("gspread/google-auth not installed or available.")

    client = _get_gspread_client_from_service_account_info(service_account)
    sh = client.open_by_key(spreadsheet_id)
    # allow passing name or index
    if isinstance(worksheet_name_or_index, int):
        ws = sh.get_worksheet(worksheet_name_or_index)
    else:
        ws = sh.worksheet(worksheet_name_or_index)
    df = pd.DataFrame(ws.get_all_records())
    return df


# ---------- Price fetching ----------

def _fetch_yf_price(symbol: str) -> Optional[float]:
    """
    Try to fetch price using yfinance (best-effort).
    """
    try:
        t = yf.Ticker(symbol)
        # try history first
        hist = t.history(period="1d")
        if hist is not None and not hist.empty:
            return float(hist["Close"][-1])
        info = t.info or {}
        p = info.get("regularMarketPrice") or info.get("currentPrice")
        if p is not None:
            return float(p)
    except Exception as e:
        logger.debug("yfinance error for %s: %s", symbol, e)
    return None


def fetch_prices(symbols: List[str], max_workers: int = 6, timeout_per_call: float = 8.0) -> Dict[str, Optional[float]]:
    """
    Fetch prices for a list of symbols concurrently using yfinance.
    Returns dict symbol -> price (float) or None on error.
    """
    results: Dict[str, Optional[float]] = {}
    symbols_unique = list(dict.fromkeys([s.strip() for s in symbols if s and isinstance(s, str)]))
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(_fetch_yf_price, sym): sym for sym in symbols_unique}
        for fut in as_completed(futures, timeout=max(10, timeout_per_call * len(futures))):
            sym = futures[fut]
            try:
                price = fut.result(timeout=timeout_per_call)
                results[sym] = price
            except Exception as e:
                logger.warning("fetch error for %s: %s", sym, e)
                results[sym] = None
    # ensure order and presence
    return {s: results.get(s) for s in symbols}


# ---------- Portfolio helpers ----------

def normalize_holdings_df(df: pd.DataFrame, symbol_col_candidates: List[str] = None,
                          qty_col_candidates: List[str] = None) -> pd.DataFrame:
    """
    Normalize a DataFrame from Google Sheets into a DataFrame with columns:
      symbol (str), qty (float)
    It will try to detect common column names.
    """
    if symbol_col_candidates is None:
        symbol_col_candidates = ["symbol", "ticker", "sym", "code"]
    if qty_col_candidates is None:
        qty_col_candidates = ["qty", "quantity", "shares", "amount"]

    # lower-case mapping
    cols = {c.lower(): c for c in df.columns}
    symbol_col = None
    qty_col = None
    for cand in symbol_col_candidates:
        if cand in cols:
            symbol_col = cols[cand]
            break
    for cand in qty_col_candidates:
        if cand in cols:
            qty_col = cols[cand]
            break

    # fallback heuristics
    if symbol_col is None:
        # pick first text-like column
        for c in df.columns:
            if df[c].dtype == object:
                symbol_col = c
                break
    if qty_col is None:
        # pick a numeric column
        for c in df.columns:
            if pd.api.types.is_numeric_dtype(df[c]):
                qty_col = c
                break

    if symbol_col is None or qty_col is None:
        raise ValueError("Could not detect symbol and qty columns automatically. Please ensure sheet has columns like 'symbol' and 'qty'.")

    out = df[[symbol_col, qty_col]].copy()
    out.columns = ["symbol", "qty"]
    out["symbol"] = out["symbol"].astype(str).str.strip()
    out["qty"] = pd.to_numeric(out["qty"], errors="coerce").fillna(0.0)
    out = out[out["symbol"].astype(bool)].reset_index(drop=True)
    return out


def compute_portfolio(holdings_df: pd.DataFrame, prices: Dict[str, Optional[float]]) -> Tuple[pd.DataFrame, float]:
    """
    Given holdings (columns: symbol, qty) and a dict of prices, return a DataFrame with price & value and total.
    """
    df = holdings_df.copy()
    df["price"] = df["symbol"].map(prices)
    df["value"] = df.apply(lambda r: (r["price"] * r["qty"]) if (r["price"] is not None and not pd.isna(r["qty"])) else None, axis=1)
    total = float(df["value"].dropna().sum()) if not df["value"].dropna().empty else 0.0
    return df, total
