from concurrent.futures import ThreadPoolExecutor, as_completed
from .models import Danmaku
from .proto.dm_pb2 import DmSegMobileReply, DmWebViewReply
from .progress import NULL_PROGRESS

def parse_segment(payload, episode_key):
    reply=DmSegMobileReply(); reply.ParseFromString(payload)
    return [Danmaku(str(e.idStr or e.id),episode_key,e.content,e.ctime,e.progress,e.fontsize,e.color,e.midHash,e.pool,mode=e.mode,weight=e.weight,action=e.action,attr=e.attr) for e in reply.elems]

class DanmakuCollector:
    VIEW_URL="https://api.bilibili.com/x/v2/dm/web/view"; SEGMENT_URL="https://api.bilibili.com/x/v2/dm/web/seg.so"
    def __init__(self,client,repository,progress=None): self.client=client; self.repository=repository; self.progress=progress or NULL_PROGRESS
    def collect(self,episode):
        payload=self.client.get_bytes(self.VIEW_URL,{"type":1,"oid":episode.cid}); view=DmWebViewReply(); view.ParseFromString(payload); total=int(view.dmSge.total)
        if total < 1: raise ValueError("弹幕分段总数缺失")
        self.repository.set_danmaku_total(episode.episode_key,total); start=self.repository.get_danmaku_next_segment(episode.episode_key)
        def fetch(segment):
            data=self.client.get_bytes(self.SEGMENT_URL,{"type":1,"oid":episode.cid,"segment_index":segment}); return segment,parse_segment(data,episode.episode_key)
        with self.progress.task("弹幕 {}".format(episode.title), total=total, initial=start-1, unit="段") as task:
            with ThreadPoolExecutor(max_workers=self.client.limiter.max_concurrency) as pool:
                for future in as_completed([pool.submit(fetch,s) for s in range(start,total+1)]):
                    segment,items=future.result(); self.repository.commit_danmaku_segment(episode.episode_key,segment,items,segment==total)
                    task.update(1, records=self.repository.count_danmaku(episode.episode_key))
        return self.repository.count_danmaku(episode.episode_key)
