import json
from concurrent.futures import ThreadPoolExecutor, as_completed

from .models import Comment
from .progress import NULL_PROGRESS


class CommentCollector:
    MAIN_URL = "https://api.bilibili.com/x/v2/reply/wbi/main"
    CHILD_URL = "https://api.bilibili.com/x/v2/reply/reply"

    def __init__(self, client, repository, progress=None):
        self.client = client
        self.repository = repository
        self.progress_reporter = progress or NULL_PROGRESS

    def _comment(self, raw, work_key, aid, root=None):
        return Comment(
            str(raw["rpid"]), work_key, aid,
            str(raw.get("mid") or raw.get("member", {}).get("mid", "")),
            raw.get("member", {}).get("uname", ""),
            raw.get("content", {}).get("message", ""),
            str(raw.get("root") or root or "") or None,
            str(raw.get("parent") or "") or None,
            int(raw.get("ctime", 0)), int(raw.get("like", 0)),
        )

    def collect(self, work_key, aid):
        state = self.repository.get_comment_progress(work_key, aid)
        cursor = state["next_cursor"]
        roots = set()
        with self.progress_reporter.task("主评论 aid={}".format(aid), unit="页") as main_task:
            while not state["complete"]:
                params = {"type": 1, "oid": aid, "mode": 3, "plat": 1}
                if cursor:
                    params["pagination_str"] = json.dumps({"offset": cursor}, separators=(",", ":"))
                data = self.client.get_json(self.MAIN_URL, params, signed=True)
                comments = []
                for raw in data.get("replies") or []:
                    root = self._comment(raw, work_key, aid)
                    comments.append(root)
                    embedded = raw.get("replies") or []
                    comments.extend(self._comment(item, work_key, aid, root.rpid) for item in embedded)
                    if int(raw.get("rcount", 0)) > len(embedded):
                        roots.add(root.rpid)
                        self.repository.commit_child_comment_page(work_key, root.rpid, [], 1, False)
                page_cursor = data.get("cursor") or {}
                complete = bool(page_cursor.get("is_end"))
                cursor = ((page_cursor.get("pagination_reply") or {}).get("next_offset") or "")
                if not complete and not cursor:
                    raise ValueError("主评论分页游标缺失")
                self.repository.commit_comment_page(work_key, aid, comments, cursor, complete)
                state = {"complete": complete, "next_cursor": cursor}
                main_task.update(1, records=self.repository.count_comments(work_key))

        roots.update(self.repository.list_pending_child_roots(work_key, aid))
        with self.progress_reporter.task("子评论 aid={}".format(aid), total=len(roots), unit="根") as child_task:
            with ThreadPoolExecutor(max_workers=self.client.limiter.max_concurrency) as pool:
                futures = [pool.submit(self._children, work_key, aid, root) for root in roots]
                for future in as_completed(futures):
                    future.result()
                    child_task.update()
        return self.repository.count_comments(work_key)

    def _children(self, work_key, aid, root):
        state = self.repository.get_child_progress(work_key, root)
        page = int(state["next_page"])
        while not state["complete"]:
            data = self.client.get_json(
                self.CHILD_URL,
                {"type": 1, "oid": aid, "root": root, "pn": page, "ps": 20},
            )
            replies = data.get("replies") or []
            comments = [self._comment(item, work_key, aid, root) for item in replies]
            info = data.get("page") or {}
            complete = not replies or page * int(info.get("size", 20)) >= int(info.get("count", 0))
            self.repository.commit_child_comment_page(work_key, root, comments, page + 1, complete)
            page += 1
            state = {"complete": complete}
