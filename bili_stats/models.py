from dataclasses import dataclass
from typing import Any, Optional, Sequence, Tuple


@dataclass(frozen=True)
class ParsedInput:
    kind: Any
    identifier: str
    page: Optional[int] = None
    owner_mid: Optional[str] = None
    original: str = ""


@dataclass(frozen=True)
class Episode:
    episode_key: str
    position: int
    title: str
    bvid: str
    aid: int
    cid: int
    ep_id: Optional[int] = None
    work_key: Optional[str] = None


@dataclass(frozen=True)
class Work:
    work_key: str
    kind: Any
    title: str
    episodes: Tuple[Episode, ...] = ()
    source_id: Optional[str] = None
    owner_mid: Optional[str] = None

    def __init__(
        self,
        work_key: str,
        kind: Any,
        title: str,
        episodes: Sequence[Episode] = (),
        source_id: Optional[str] = None,
        owner_mid: Optional[str] = None,
    ) -> None:
        object.__setattr__(self, "work_key", work_key)
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "title", title)
        object.__setattr__(self, "episodes", tuple(episodes))
        object.__setattr__(self, "source_id", source_id)
        object.__setattr__(self, "owner_mid", owner_mid)


@dataclass(frozen=True)
class Danmaku:
    danmaku_id: str
    episode_key: str
    content: str
    ctime: int
    progress: int
    fontsize: int
    color: int
    sender_hash: str
    pool: int
    mode: int = 1
    weight: int = 0
    action: str = ""
    attr: int = 0


@dataclass(frozen=True)
class Comment:
    rpid: str
    work_key: str
    aid: int
    user_mid: str
    user_name: str
    content: str
    root_rpid: Optional[str] = None
    parent_rpid: Optional[str] = None
    ctime: int = 0
    likes: int = 0

