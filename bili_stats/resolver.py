from .input import InputKind
from .models import Episode, Work

class Resolver:
    def __init__(self,client): self.client=client
    def resolve(self,parsed):
        if parsed.kind==InputKind.VIDEO: return self._video(parsed.identifier)
        if parsed.kind==InputKind.COLLECTION: return self._collection(parsed.owner_mid,parsed.identifier)
        return self._bangumi(parsed)
    def _video(self,bvid):
        data=self.client.get_json("https://api.bilibili.com/x/web-interface/view",{"bvid":bvid}); pages=data.get("pages") or [{"cid":data["cid"],"page":1,"part":data["title"]}]; key="video:"+data["bvid"]
        episodes=tuple(Episode("cid:{}".format(p["cid"]),p.get("page",i),p.get("part") or "P{}".format(i),data["bvid"],data["aid"],p["cid"],work_key=key) for i,p in enumerate(pages,1))
        source={
            "bvid": data.get("bvid"), "aid": data.get("aid"), "title": data.get("title"),
            "desc": data.get("desc", ""), "owner": data.get("owner") or {}, "stat": data.get("stat") or {},
        }
        return Work(key,InputKind.VIDEO,data["title"],episodes,data["bvid"],source=source)
    def _collection(self,mid,season_id):
        archives=[]; page=1; data={}
        while True:
            data=self.client.get_json("https://api.bilibili.com/x/polymer/web-space/seasons_archives_list",{"mid":mid,"season_id":season_id,"page_num":page,"page_size":30,"sort_reverse":"false"}); batch=data.get("archives") or []; archives.extend(batch)
            if len(batch)<30: break
            page+=1
        key="collection:{}:{}".format(mid,season_id); episodes=[]
        for archive in archives:
            for item in self._video(archive["bvid"]).episodes: episodes.append(Episode(item.episode_key,len(episodes)+1,item.title,item.bvid,item.aid,item.cid,work_key=key))
        return Work(key,InputKind.COLLECTION,(data.get("meta") or {}).get("name") or "合集"+season_id,episodes,season_id,mid)
    def _bangumi(self,parsed):
        params={"ep_id" if parsed.kind==InputKind.EPISODE else "season_id":parsed.identifier}; data=self.client.get_json("https://api.bilibili.com/pgc/view/web/season",params); season_id=str(data.get("season_id") or parsed.identifier); key="season:"+season_id
        episodes=tuple(Episode("cid:{}".format(e["cid"]),i,e.get("long_title") or e.get("title") or "EP{}".format(i),e.get("bvid",""),e["aid"],e["cid"],e.get("id"),key) for i,e in enumerate(data.get("episodes") or [],1))
        return Work(key,InputKind.SEASON,data.get("season_title") or data.get("title") or "番剧"+season_id,episodes,season_id)
