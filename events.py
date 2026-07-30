"""Calendario economico ad alto impatto per l'oro (fonte gratuita ForexFactory).

NON prevede la direzione: serve solo a sapere QUANDO ci sono eventi che creano
alta volatilita' sull'oro (CPI, FOMC, NFP, GDP...), per gestire il rischio.
L'oro e' guidato soprattutto dal dollaro: filtriamo eventi USD ad alto impatto.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone

import requests

_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
_CACHE: dict = {"t": 0.0, "events": []}


def _parse(raw: list) -> list[dict]:
    out = []
    for e in raw:
        if e.get("country") != "USD" or e.get("impact") != "High":
            continue
        try:
            dt = datetime.fromisoformat(e["date"]).astimezone(timezone.utc)
        except Exception:
            continue
        title = e.get("title", "?")
        out.append({
            "title": title,
            "country": e.get("country", ""),
            "dt": dt,
            "forecast": e.get("forecast") or "-",
            "previous": e.get("previous") or "-",
            "key": f"{title}|{dt.strftime('%Y-%m-%dT%H:%M')}",
        })
    out.sort(key=lambda x: x["dt"])
    return out


def get_events(ttl: int = 1800) -> list[dict]:
    """Eventi USD ad alto impatto della settimana (con cache di 30 min)."""
    now = time.time()
    if _CACHE["events"] and now - _CACHE["t"] < ttl:
        return _CACHE["events"]
    try:
        r = requests.get(_URL, headers=_HEADERS, timeout=25)
        r.raise_for_status()
        evs = _parse(r.json())
        _CACHE["events"] = evs
        _CACHE["t"] = now
        return evs
    except Exception:
        return _CACHE["events"]  # in caso di errore, usa la cache (anche se vecchia)


def upcoming(minutes: int, now: datetime | None = None) -> list[dict]:
    """Eventi che iniziano da adesso a 'minutes' minuti nel futuro."""
    now = now or datetime.now(timezone.utc)
    lo, hi = now, now.timestamp() + minutes * 60
    return [e for e in get_events() if now <= e["dt"] and e["dt"].timestamp() <= hi]


def today_events(now: datetime | None = None) -> list[dict]:
    """Eventi ad alto impatto ancora da venire nella giornata UTC corrente."""
    now = now or datetime.now(timezone.utc)
    return [e for e in get_events() if e["dt"].date() == now.date() and e["dt"] >= now]


def format_headsup(e: dict) -> str:
    return (
        "📅⚠️ <b>Evento ad alto impatto in arrivo</b>\n"
        f"<b>{e['title']}</b> ({e['country']})\n"
        f"Orario: <b>{e['dt'].strftime('%H:%M')} UTC</b>\n"
        f"Atteso: {e['forecast']} · Precedente: {e['previous']}\n\n"
        "⚠️ Alta volatilità attesa sull'oro. Valuta di <b>non aprire</b> nuovi "
        "trade o <b>ridurre la size</b> fino a dopo il dato.\n"
        "<i>Non è una previsione di direzione. Non è consulenza finanziaria.</i>"
    )


def format_agenda(events: list[dict]) -> str:
    if not events:
        return ("📅 <b>Agenda oro — oggi</b>\nNessun evento USD ad alto impatto "
                "previsto oggi. Giornata più tranquilla lato news.")
    lines = ["📅 <b>Agenda oro — oggi (eventi ad alto impatto)</b>", ""]
    for e in events:
        lines.append(f"• <b>{e['dt'].strftime('%H:%M')} UTC</b> — {e['title']} (atteso {e['forecast']})")
    lines += ["", "<i>Attorno a questi orari, alta volatilità sull'oro: gestisci il "
              "rischio. Non è consulenza finanziaria.</i>"]
    return "\n".join(lines)
