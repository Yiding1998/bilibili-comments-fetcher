import re
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

from .progress import NULL_PROGRESS


EXCEL_CELL_LIMIT = 32767
TRUNCATION_MARKER = "...[内容已截断]"
UNKNOWN_IDENTITY = "(未知)"
INVALID_EXCEL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def excel_text(parts):
    text = "\n".join("" if part is None else str(part) for part in parts)
    if len(text) <= EXCEL_CELL_LIMIT:
        return text
    return text[: EXCEL_CELL_LIMIT - len(TRUNCATION_MARKER)] + TRUNCATION_MARKER


def excel_cell(value):
    if not isinstance(value, str):
        return value
    return excel_text([INVALID_EXCEL_CHARS.sub("", value)])

def build_danmaku_user_rows(rows):
    groups = defaultdict(list)
    for row in rows:
        identity = str(row.get("sender_hash") or UNKNOWN_IDENTITY)
        groups[identity].append(row.get("content", ""))
    ordered = sorted(groups.items(), key=lambda item: (-len(item[1]), item[0]))
    return [
        {"排名": rank, "发送者标识": identity, "发送者哈希": identity, "弹幕次数": len(contents), "弹幕内容": excel_text(contents)}
        for rank, (identity, contents) in enumerate(ordered, 1)
    ]


def build_comment_user_rows(rows):
    groups = defaultdict(list)
    names = defaultdict(list)
    for index, row in enumerate(rows):
        identity = str(row.get("user_mid") or UNKNOWN_IDENTITY)
        groups[identity].append(row.get("content", ""))
        name = str(row.get("user_name") or "")
        if name:
            names[identity].append((int(row.get("ctime") or 0), index, name))
    ordered = sorted(groups.items(), key=lambda item: (-len(item[1]), item[0]))
    result = []
    for rank, (identity, contents) in enumerate(ordered, 1):
        result.append({
            "排名": rank,
            "用户MID": identity,
            "用户名": max(names.get(identity, [(0, 0, UNKNOWN_IDENTITY)]))[2],
            "评论次数": len(contents),
            "评论内容": excel_text(contents),
        })
    return result


def safe_name(value):
    value = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", str(value)).strip(" .")
    return value[:120] or "未命名"


def _write(path, rows):
    frame = pd.DataFrame(rows)
    if not frame.empty:
        frame = frame.applymap(excel_cell)
    frame.to_excel(str(path), index=False, engine="openpyxl")


def export(repository, work_key, output_root, progress=None):
    work = repository.get_work(work_key)
    if not work:
        raise ValueError("数据库中不存在任务 " + work_key)
    root = Path(output_root) / safe_name(work["title"])
    root.mkdir(parents=True, exist_ok=True)
    episodes = repository.list_episodes(work_key)
    all_danmaku = repository.list_danmaku(work_key)
    comments = repository.list_comments(work_key)
    reporter = progress or NULL_PROGRESS
    total_files = len(episodes) * 5 + 5

    with reporter.task("导出 Excel", total=total_files, unit="文件") as task:
        def write(path, rows):
            _write(path, rows)
            task.update()

        for episode in episodes:
            folder = root / "{:02d}-{}".format(episode["position"], safe_name(episode["title"]))
            folder.mkdir(parents=True, exist_ok=True)
            rows = [row for row in all_danmaku if row["episode_key"] == episode["episode_key"]]
            write(folder / "弹幕明细.xlsx", rows)
            write(folder / "弹幕统计.xlsx", [{"弹幕内容": key, "出现次数": value} for key, value in Counter(row["content"] for row in rows).most_common()])
            write(folder / "弹幕用户排行.xlsx", build_danmaku_user_rows(rows))
            write(folder / "完整评论.xlsx", comments)
            write(folder / "评论用户统计.xlsx", [{"用户名": key, "评论次数": value} for key, value in Counter(row["user_name"] for row in comments).most_common()])
        write(root / "全局弹幕统计.xlsx", [{"弹幕内容": key, "出现次数": value} for key, value in Counter(row["content"] for row in all_danmaku).most_common()])
        write(root / "全局弹幕用户排行.xlsx", build_danmaku_user_rows(all_danmaku))
        write(root / "全局评论统计.xlsx", [{"用户名": key, "评论次数": value} for key, value in Counter(row["user_name"] for row in comments).most_common()])
        write(root / "评论用户排行.xlsx", build_comment_user_rows(comments))
        write(root / "分集概览.xlsx", [{"序号": episode["position"], "标题": episode["title"], "BVID": episode["bvid"], "CID": episode["cid"], "弹幕条数": sum(1 for row in all_danmaku if row["episode_key"] == episode["episode_key"])} for episode in episodes])
    return root
