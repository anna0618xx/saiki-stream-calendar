"""Read date-confirmable public goods announcements from Saiki's Nijisanji Wiki.

Fan wiki text is unverified: every result is a REVIEW CANDIDATE only.
Never access member-only pages, accounts, local savings or screenshots.
"""
from __future__ import annotations
import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from bs4 import BeautifulSoup
from collect import fetch_bytes

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "goods_candidates.json"
WIKI_SCHEDULE = "https://wikiwiki.jp/nijisanji/佐伯イッテツ/スケジュール"
WIKI_PROMO = "https://wikiwiki.jp/nijisanji/佐伯イッテツ"
WIKI_ADVERT = "https://wikiwiki.jp/nijisanji/佐伯イッテツ/宣伝"
JST = timezone(timedelta(hours=9))
DATE = re.compile(r"(?:(20\d{2})年)?(\d{1,2})月(\d{1,2})日(?:[（(][^）)]{1,5}[）)])?\s*(?:(\d{1,2})(?:[:時](\d{1,2}))?分?)?")
CATEGORY = re.compile(r"グッズ|受注|販売|発売|予約|ボイス|アルバム")
TIMING = re.compile(r"販売期間|受注|予約|締切|〆切|販売開始|販売終了|発売日|申込期限")
ACTIVE_TITLE = re.compile(r"グッズ|ボイス|アルバム|CD|ぬい|商品|周年|パペット|MECHATU|Over Drive", re.I)


def dates_in_line(line: str, year: int):
    found = []
    for m in DATE.finditer(line):
        y = int(m.group(1) or year)
        mo, day = int(m.group(2)), int(m.group(3))
        try:
            datetime(y, mo, day)
        except ValueError:
            continue
        hour, minute = m.group(4), m.group(5)
        # Source explicitly provides hour:minute or hour時; never infer missing hour.
        if hour is not None:
            h = int(hour)
            mm = int(minute or 0)
            if not(0 <= h <= 23 and 0 <= mm <= 59):
                continue
            stamp = f"{y:04d}-{mo:02d}-{day:02d}T{h:02d}:{mm:02d}"
        else:
            stamp = f"{y:04d}-{mo:02d}-{day:02d}"
        found.append(stamp)
    return found


def candidate(title: str, date: str, kind: str, page: str, note: str = ""):
    if kind not in ("deadline", "reserveStart", "release"):
        return None
    name = re.sub(r"\s+", " ", title).strip().strip("▶︎■:：")
    if not name or len(name) > 180:
        return None
    key = hashlib.sha1(name.encode("utf-8")).hexdigest()[:10]
    return dict(id=f"wiki-{kind}-{date[:10]}-{key}",title=name,date=date,kind=kind,
                sourceUrl=page,detailUrl="",source="nijisanji-wiki",
                note=note[:220])


def extract_goods_from_schedule(page: bytes, url: str, year: int):
    """Only the last 'remarks' column: no YouTube member/title harvesting."""
    soup = BeautifulSoup(page, "html.parser")
    found = []
    for tr in soup.find_all("tr"):
        cells = tr.find_all(["td", "th"], recursive=False)
        if len(cells) < 5:
            continue
        first = cells[0].get_text(" ", strip=True)
        md = re.search(r"(\d{1,2})月(\d{1,2})日", first)
        if not md:
            continue
        mo, day = int(md.group(1)), int(md.group(2))
        try:
            datetime(year, mo, day)
        except ValueError:
            continue
        remarks = cells[-1].get_text(" ", strip=True)
        if not CATEGORY.search(remarks):
            continue
        # A date-oriented remark, not a purchase link, with no invented hour.
        items = re.split(r"[。／\n]", remarks)
        for part in items:
            if not CATEGORY.search(part):
                continue
            if re.search(r"終了|締切|〆切", part):
                kind = "deadline"
            elif re.search(r"発売日|発売$", part):
                kind = "release"
            elif re.search(r"開始", part):
                kind = "reserveStart"
            else:
                continue
            when = f"{year:04d}-{mo:02d}-{day:02d}"
            # If a time is unambiguously attached to this day's note, retain it.
            time = re.search(r"(?:当日|本日)?\s*(\d{1,2})(?::|時)(\d{2})?(?:分)?(?:開始|終了|まで)?", part)
            if time:
                hh, mm = int(time.group(1)), int(time.group(2) or 0)
                if 0 <= hh <= 23 and 0 <= mm <= 59:
                    when += f"T{hh:02d}:{mm:02d}"
            title = re.sub(r"(?:受注|予約|販売)(?:開始|終了)|発売日|発売|締切|〆切|開始|終了", "", part)
            title = re.sub(r"(?:～|〜)\s*\d{1,2}/\d{1,2}", "", title)
            title = title.strip(" 　・:：()（）")
            if len(title) < 4 or len(title) > 170:
                continue
            row = candidate(title, when, kind, url, remarks)
            if row:
                found.append(row)
    return found


def extract_goods_from_announcements(page: bytes, url: str, year: int):
    """Use date-labeled list items inside goods/merch headings, not arbitrary dates."""
    soup = BeautifulSoup(page, "html.parser")
    found = []
    in_goods = False
    title = ""
    for node in soup.find_all(["h3", "h4", "h5", "li"]):
        if node.name == "h3":
            heading = node.get_text(" ", strip=True)
            in_goods = "グッズ情報" in heading
            title = ""
        elif node.name in ("h4", "h5"):
            label = node.get_text(" ", strip=True)
            if in_goods and ACTIVE_TITLE.search(label):
                title = label[:180]
        elif node.name == "li" and in_goods and title:
            # Nested list items must not double-emit from their parent.
            line = node.get_text(" ", strip=True)
            if len(line) > 320 or not TIMING.search(line):
                continue
            matches = dates_in_line(line,year)
            if not matches:
                continue
            # A sale period has a distinct start and end; look at both.
            if len(matches) >= 2 and re.search(r"期間|受注|～|〜", line):
                events = [("reserveStart",matches[0]),("deadline",matches[-1])]
            elif re.search(r"締切|〆切|終了|まで",line):
                events = [("deadline",matches[-1])]
            elif re.search(r"発売日",line):
                events = [("release",matches[0])]
            else:
                events = [("reserveStart",matches[0])]
            for kind,when in events:
                row=candidate(title,when,kind,url,line)
                if row:
                    found.append(row)
    return found


def main():
    today = datetime.now(JST).date()
    first = (today-timedelta(days=1)).isoformat()
    last = (today+timedelta(days=365)).isoformat()
    old = {"candidates":[]}
    if OUT.exists():
        try:
            old = json.loads(OUT.read_text(encoding="utf-8"))
        except (ValueError,OSError):
            pass
    gathered = []
    for url, parser in [(WIKI_SCHEDULE,extract_goods_from_schedule),
                        (WIKI_PROMO,extract_goods_from_announcements),
                        (WIKI_ADVERT,extract_goods_from_announcements)]:
        try:
            rows=parser(fetch_bytes(url,timeout=25),url,today.year)
            print("Wiki goods extracted:",url,len(rows))
            gathered.extend(rows)
        except (HTTPError,URLError,TimeoutError,OSError,ValueError) as err:
            print("Wiki goods source unavailable:",url,repr(err))
    by_id = {}
    for item in [*old.get("candidates",[]),*gathered]:
        if not isinstance(item,dict):
            continue
        day=str(item.get("date",""))[:10]
        if first <= day <= last and item.get("id") and item.get("kind") in ("deadline","reserveStart","release"):
            by_id[item["id"]]=item
    candidates=sorted(by_id.values(),key=lambda x:(x["date"],x["title"]))[:90]
    # Avoid replacing useful cached results just because Wiki was temporarily inaccessible.
    raw={"generatedAt":datetime.now(JST).isoformat(),"candidates":candidates,
         "notice":"Public Wiki-derived hints only; verify details before manually saving."}
    OUT.write_text(json.dumps(raw,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("Wrote Wiki goods candidates:",len(candidates))


if __name__=="__main__":
    main()
