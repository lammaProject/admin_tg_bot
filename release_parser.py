from __future__ import annotations

import json
import random
import re
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Iterable
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, Tag
from zoneinfo import ZoneInfo


RELEASES_URL = "https://risazatvorchestvo.com/releases"
DEFAULT_TIMEZONE = "Asia/Yekaterinburg"

MONTHS_RU = {
    "января": 1,
    "февраля": 2,
    "марта": 3,
    "апреля": 4,
    "мая": 5,
    "июня": 6,
    "июля": 7,
    "августа": 8,
    "сентября": 9,
    "октября": 10,
    "ноября": 11,
    "декабря": 12,
}


class ReleaseParserError(RuntimeError):
    pass


@dataclass(frozen=True)
class Release:
    artist: str
    title: str
    points: str
    url: str


def get_yesterday(timezone: str = DEFAULT_TIMEZONE) -> date:
    return datetime.now(ZoneInfo(timezone)).date() - timedelta(days=1)


def fetch_yesterdays_releases(
    url: str = RELEASES_URL,
    *,
    timezone: str = DEFAULT_TIMEZONE,
    timeout: int = 20,
    attempts: int = 3,
    retry_delay: float = 2.0,
) -> list[Release]:
    target_date = get_yesterday(timezone)
    html = fetch_releases_page(url, timeout=timeout, attempts=attempts, retry_delay=retry_delay)
    return parse_releases(html, base_url=url, target_date=target_date)


def fetch_releases_page(
    url: str = RELEASES_URL,
    *,
    timeout: int = 20,
    attempts: int = 3,
    retry_delay: float = 2.0,
) -> str:
    last_error: Exception | None = None

    for attempt in range(1, max(1, attempts) + 1):
        try:
            response = requests.get(
                url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
                    ),
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
                },
                timeout=timeout,
            )
            response.raise_for_status()

            html = response.text
            if is_captcha_page(html):
                raise ReleaseParserError(
                    "Сайт risazatvorchestvo.com отдал страницу Yandex SmartCaptcha вместо релизов."
                )

            return html
        except (requests.RequestException, ReleaseParserError) as error:
            last_error = error
            if attempt < max(1, attempts):
                time.sleep(retry_delay * attempt + random.uniform(0, 0.75))

    raise ReleaseParserError(
        f"Не удалось получить страницу релизов после {max(1, attempts)} попыток: {last_error}"
    ) from last_error


def parse_releases(html: str, *, base_url: str, target_date: date) -> list[Release]:
    soup = BeautifulSoup(html, "html.parser")
    releases = [
        *_parse_json_releases(soup, base_url=base_url, target_date=target_date),
        *_parse_html_releases(soup, base_url=base_url, target_date=target_date),
    ]

    unique_releases: list[Release] = []
    seen: set[tuple[str, str, str]] = set()
    for release in releases:
        key = (release.artist.lower(), release.title.lower(), release.url)
        if key in seen:
            continue
        seen.add(key)
        unique_releases.append(release)

    return unique_releases


def format_releases_message(releases: Iterable[Release], target_date: date) -> str:
    releases = list(releases)
    formatted_date = target_date.strftime("%d.%m.%Y")

    if not releases:
        return f"Новых релизов за {formatted_date} не найдено."

    lines = [f"Новые релизы за {formatted_date}:"]
    for index, release in enumerate(releases, start=1):
        points = f" ({release.points})" if release.points else ""
        title = f" - {release.title}" if release.title and release.title != release.artist else ""
        url = f"\n{release.url}" if release.url else ""
        lines.append(f"{index}. {release.artist}{points}{title}{url}")

    return "\n\n".join(lines)


def split_telegram_message(text: str, limit: int = 4096) -> list[str]:
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    current = ""
    for block in text.split("\n\n"):
        separator = "\n\n" if current else ""
        if len(current) + len(separator) + len(block) <= limit:
            current = f"{current}{separator}{block}"
            continue

        if current:
            chunks.append(current)
        current = block[:limit]

    if current:
        chunks.append(current)

    return chunks


def is_captcha_page(html: str) -> bool:
    lowered = html.lower()
    return any(
        marker in lowered
        for marker in (
            "smartcaptcha",
            "checkbox-captcha-form",
            "are you not a robot",
            "вы не робот",
        )
    )


def _parse_html_releases(soup: BeautifulSoup, *, base_url: str, target_date: date) -> list[Release]:
    cards: list[Tag] = []
    for node in soup.find_all(string=True):
        parent = node.parent
        if not isinstance(parent, Tag) or parent.name in {"script", "style"}:
            continue
        if _extract_date(_normalize_text(str(node)), default_year=target_date.year) != target_date:
            continue
        card = _find_release_card(parent)
        if card not in cards:
            cards.append(card)

    return [_release_from_card(card, base_url=base_url) for card in cards]


def _parse_json_releases(soup: BeautifulSoup, *, base_url: str, target_date: date) -> list[Release]:
    releases: list[Release] = []

    for script in soup.find_all("script"):
        raw = script.string or script.get_text(strip=True)
        raw = raw.strip()
        if not raw:
            continue

        json_payloads = []
        if script.get("type") == "application/ld+json" or raw.startswith(("{", "[")):
            json_payloads.append(raw)
        elif "__NEXT_DATA__" in raw:
            match = re.search(r"<script[^>]*id=[\"']__NEXT_DATA__[\"'][^>]*>(.*?)</script>", str(script), re.S)
            if match:
                json_payloads.append(match.group(1))

        for payload in json_payloads:
            try:
                data = json.loads(payload)
            except json.JSONDecodeError:
                continue
            for item in _walk_json_objects(data):
                release = _release_from_json_object(item, base_url=base_url, target_date=target_date)
                if release:
                    releases.append(release)

    return releases


def _walk_json_objects(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_json_objects(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_json_objects(child)


def _release_from_json_object(item: dict[str, Any], *, base_url: str, target_date: date) -> Release | None:
    date_value = _first_value(item, ("date", "releaseDate", "releasedAt", "publishedAt", "createdAt"))
    if _extract_date(str(date_value or ""), default_year=target_date.year) != target_date:
        return None

    artist = _first_value(item, ("artist", "artistName", "author", "performer", "musician")) or ""
    if isinstance(artist, dict):
        artist = _first_value(artist, ("name", "title")) or ""

    title = _first_value(item, ("album", "albumTitle", "releaseTitle", "title", "name")) or ""
    if isinstance(title, dict):
        title = _first_value(title, ("name", "title")) or ""

    points = _first_value(item, ("points", "score", "rating", "value")) or ""
    url = _first_value(item, ("url", "href", "link", "slug")) or ""

    return Release(
        artist=_clean_value(str(artist)) or "Неизвестный артист",
        title=_clean_value(str(title)),
        points=_format_points(str(points)),
        url=_absolute_url(str(url), base_url),
    )


def _release_from_card(card: Tag, *, base_url: str) -> Release:
    artist = _text_by_attr(card, ("artist", "author", "performer", "musician"))
    title = _text_by_attr(card, ("album", "release-title", "title", "name"))
    points = _text_by_attr(card, ("points", "score", "rating", "value"))
    url = _release_url(card, base_url)

    link_texts = _unique_texts(
        link.get_text(" ", strip=True)
        for link in card.find_all("a")
        if link.get_text(" ", strip=True)
    )

    if not title:
        title = _heading_text(card) or _text_for_url(card, url)

    if not artist:
        for text in link_texts:
            if text != title and _extract_date(text) is None and not _looks_like_points(text):
                artist = text
                break

    text_lines = _card_text_lines(card)
    if not points:
        points = _extract_points(" ".join(text_lines))

    if not title:
        title = _first_content_line(text_lines, excluded={artist, points})

    if not artist and title:
        artist = title

    return Release(
        artist=_clean_value(artist) or "Неизвестный артист",
        title=_clean_value(title),
        points=_format_points(points),
        url=url,
    )


def _find_release_card(node: Tag) -> Tag:
    current = node
    best = node
    while isinstance(current, Tag) and current.name not in {"html", "body"}:
        class_text = " ".join(current.get("class", []))
        identity = f"{current.name} {class_text} {current.get('id', '')}".lower()
        has_link = current.find("a", href=True) is not None
        if current.name in {"article", "li", "tr"} and has_link:
            return current
        if has_link and re.search(r"release|album|card|item|row", identity):
            return current
        if has_link:
            best = current
        current = current.parent
    return best


def _text_by_attr(card: Tag, attr_markers: tuple[str, ...]) -> str:
    for element in card.find_all(True):
        attrs = " ".join(
            str(value)
            for key, value in element.attrs.items()
            if key in {"class", "id", "itemprop", "data-testid", "data-test", "aria-label"}
        ).lower()
        if any(marker in attrs for marker in attr_markers):
            text = element.get_text(" ", strip=True)
            if text and _extract_date(text) is None:
                return text
    return ""


def _heading_text(card: Tag) -> str:
    heading = card.find(re.compile("^h[1-6]$"))
    return heading.get_text(" ", strip=True) if heading else ""


def _release_url(card: Tag, base_url: str) -> str:
    links = card.find_all("a", href=True)
    for link in links:
        href = str(link["href"])
        if "release" in href or "album" in href:
            return _absolute_url(href, base_url)
    if links:
        return _absolute_url(str(links[0]["href"]), base_url)
    return ""


def _text_for_url(card: Tag, url: str) -> str:
    if not url:
        return ""
    for link in card.find_all("a", href=True):
        if _absolute_url(str(link["href"]), url) == url:
            return link.get_text(" ", strip=True)
    return ""


def _card_text_lines(card: Tag) -> list[str]:
    return [
        line
        for line in _unique_texts(card.get_text("\n", strip=True).splitlines())
        if line and _extract_date(line) is None
    ]


def _first_content_line(lines: list[str], excluded: set[str]) -> str:
    excluded = {_clean_value(value) for value in excluded if value}
    for line in lines:
        clean_line = _clean_value(line)
        if clean_line and clean_line not in excluded and not _looks_like_points(clean_line):
            return clean_line
    return ""


def _extract_points(text: str) -> str:
    match = re.search(r"(\d+(?:[,.]\d+)?)\s*(балл(?:а|ов)?|points?|pts?)", text, re.I)
    return match.group(0) if match else ""


def _format_points(points: str) -> str:
    points = _clean_value(points)
    if not points:
        return ""
    if _looks_like_points(points):
        return points
    if re.fullmatch(r"\d+(?:[,.]\d+)?", points):
        return f"{points} баллов"
    return points


def _looks_like_points(text: str) -> bool:
    return bool(re.search(r"\d+(?:[,.]\d+)?\s*(балл|points?|pts?)", text, re.I))


def _extract_date(text: str, *, default_year: int | None = None) -> date | None:
    text = _normalize_text(text)

    match = re.search(r"\b(20\d{2})-(\d{1,2})-(\d{1,2})\b", text)
    if match:
        return _safe_date(int(match.group(1)), int(match.group(2)), int(match.group(3)))

    match = re.search(r"\b(\d{1,2})[./-](\d{1,2})[./-](20\d{2}|\d{2})\b", text)
    if match:
        year = int(match.group(3))
        if year < 100:
            year += 2000
        return _safe_date(year, int(match.group(2)), int(match.group(1)))

    month_names = "|".join(MONTHS_RU)
    match = re.search(rf"\b(\d{{1,2}})\s+({month_names})(?:\s+(20\d{{2}}))?\b", text, re.I)
    if match:
        year = int(match.group(3)) if match.group(3) else default_year or datetime.now().year
        return _safe_date(year, MONTHS_RU[match.group(2).lower()], int(match.group(1)))

    return None


def _safe_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _clean_value(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _unique_texts(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        clean_value = _clean_value(value)
        if not clean_value or clean_value in seen:
            continue
        seen.add(clean_value)
        result.append(clean_value)
    return result


def _absolute_url(url: str, base_url: str) -> str:
    url = _clean_value(url)
    if not url:
        return ""
    return urljoin(base_url, url)


def _first_value(item: dict[str, Any], keys: tuple[str, ...]) -> Any:
    lowered_keys = {key.lower(): key for key in item.keys()}
    for key in keys:
        actual_key = lowered_keys.get(key.lower())
        if actual_key:
            return item[actual_key]
    return None
