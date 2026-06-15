import re
from enum import Enum
from urllib.parse import parse_qs, urlparse

from .models import ParsedInput


class InputKind(str, Enum):
    VIDEO = "video"
    COLLECTION = "collection"
    EPISODE = "episode"
    SEASON = "season"


_BVID_RE = re.compile(r"BV[0-9A-Za-z]+")
_BANGUMI_RE = re.compile(r"(ep|ss)([0-9]+)")
_VIDEO_PATH_RE = re.compile(r"/video/(BV[0-9A-Za-z]+)/?")
_BANGUMI_PATH_RE = re.compile(r"/bangumi/play/(ep|ss)([0-9]+)/?")
_COLLECTION_PATH_RE = re.compile(r"/([0-9]+)/lists/([0-9]+)/?")


def _error(value: str) -> ValueError:
    return ValueError("无法识别的B站输入: {}".format(value))


def _parse_page(query: str, original: str):
    values = parse_qs(query, keep_blank_values=True)
    if "p" not in values:
        return None
    pages = values["p"]
    if len(pages) != 1 or not pages[0].isdigit() or int(pages[0]) < 1:
        raise _error(original)
    return int(pages[0])


def parse_input(value: str) -> ParsedInput:
    if not isinstance(value, str):
        raise _error(str(value))
    original = value.strip()
    if not original:
        raise _error(original)

    if _BVID_RE.fullmatch(original):
        return ParsedInput(InputKind.VIDEO, original, original=original)

    bangumi = _BANGUMI_RE.fullmatch(original)
    if bangumi:
        kind = InputKind.EPISODE if bangumi.group(1) == "ep" else InputKind.SEASON
        return ParsedInput(kind, bangumi.group(2), original=original)

    parsed = urlparse(original)
    if parsed.scheme not in ("http", "https"):
        raise _error(original)
    host = (parsed.hostname or "").lower()

    if host in ("bilibili.com", "www.bilibili.com"):
        video = _VIDEO_PATH_RE.fullmatch(parsed.path)
        if video:
            return ParsedInput(
                InputKind.VIDEO,
                video.group(1),
                page=_parse_page(parsed.query, original),
                original=original,
            )
        bangumi = _BANGUMI_PATH_RE.fullmatch(parsed.path)
        if bangumi:
            kind = InputKind.EPISODE if bangumi.group(1) == "ep" else InputKind.SEASON
            return ParsedInput(kind, bangumi.group(2), original=original)

    if host == "space.bilibili.com":
        collection = _COLLECTION_PATH_RE.fullmatch(parsed.path)
        query = parse_qs(parsed.query)
        if collection and query.get("type") == ["season"]:
            return ParsedInput(
                InputKind.COLLECTION,
                collection.group(2),
                owner_mid=collection.group(1),
                original=original,
            )

    raise _error(original)
