import hashlib
import random
import threading
import time
from functools import reduce
from urllib.parse import urlencode

import requests


MIXIN_KEY_ENC_TAB = [46,47,18,2,53,8,23,32,15,50,10,31,58,3,45,35,27,43,5,49,33,9,42,19,29,28,14,39,12,38,41,13,37,48,7,16,24,55,40,61,26,17,0,1,60,51,30,4,22,25,54,21,56,59,6,63,57,62,11,36,20,34,44,52]


def encode_wbi(params, img_key, sub_key, timestamp=None):
    source = dict(params)
    source["wts"] = int(time.time() if timestamp is None else timestamp)
    source = {key: "".join(ch for ch in str(value) if ch not in "!'()*") for key, value in source.items()}
    mixin = reduce(lambda value, index: value + (img_key + sub_key)[index], MIXIN_KEY_ENC_TAB, "")[:32]
    query = urlencode(sorted(source.items()))
    source["w_rid"] = hashlib.md5((query + mixin).encode("utf-8")).hexdigest()
    source["wts"] = int(source["wts"])
    return source


class AdaptiveLimiter:
    def __init__(self, initial_concurrency=6, max_concurrency=8, min_delay=0.05, recovery_successes=20):
        self.max_concurrency = max(1, max_concurrency)
        self.concurrency = min(max(1, initial_concurrency), self.max_concurrency)
        self.min_delay = max(0.0, min_delay)
        self.recovery_successes = max(1, recovery_successes)
        self._successes = 0
        self._last_request = 0.0
        self._lock = threading.RLock()
        self._condition = threading.Condition(self._lock)
        self._active = 0

    def acquire(self):
        with self._condition:
            while self._active >= self.concurrency:
                self._condition.wait()
            self._active += 1

    def release(self):
        with self._condition:
            self._active -= 1
            self._condition.notify_all()

    def wait(self):
        with self._lock:
            delay = self.min_delay - (time.monotonic() - self._last_request)
            if delay > 0:
                time.sleep(delay)
            self._last_request = time.monotonic()

    def record_throttle(self):
        with self._lock:
            self.concurrency = max(1, self.concurrency // 2)
            self.min_delay = min(5.0, max(0.2, self.min_delay * 2))
            self._successes = 0

    def record_success(self):
        with self._lock:
            self._successes += 1
            if self._successes >= self.recovery_successes:
                self.concurrency = min(self.max_concurrency, self.concurrency + 1)
                self.min_delay = max(0.05, self.min_delay * 0.8)
                self._successes = 0


class BilibiliError(RuntimeError):
    pass


class BilibiliClient:
    def __init__(self, cookie=None, max_attempts=5, limiter=None, session=None):
        self.max_attempts = max_attempts
        self.limiter = limiter or AdaptiveLimiter()
        self.session = session or requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
            "Referer": "https://www.bilibili.com/",
            "Accept": "application/json, text/plain, */*",
        })
        if cookie:
            self.session.headers["Cookie"] = cookie
        self._wbi_keys = None

    def _request(self, url, params=None, binary=False):
        last_error = None
        for attempt in range(self.max_attempts):
            self.limiter.acquire()
            try:
                self.limiter.wait()
                response = self.session.get(url, params=params, timeout=20)
                if response.status_code in (412, 429) or response.status_code >= 500:
                    self.limiter.record_throttle()
                    raise BilibiliError("temporary HTTP {}".format(response.status_code))
                response.raise_for_status()
                payload = response.content if binary else response.json()
                if not binary and payload.get("code") in (-412, -429):
                    self.limiter.record_throttle()
                    raise BilibiliError("temporary API {}".format(payload.get("code")))
                self.limiter.record_success()
                return payload
            except (requests.RequestException, ValueError, BilibiliError) as exc:
                last_error = exc
                if attempt + 1 >= self.max_attempts:
                    break
                time.sleep(min(30.0, (2 ** attempt) + random.random()))
            finally:
                self.limiter.release()
        raise BilibiliError("request failed: {}".format(last_error))

    def get_json(self, url, params=None, signed=False):
        if signed:
            img, sub = self.get_wbi_keys()
            params = encode_wbi(params or {}, img, sub)
        data = self._request(url, params=params)
        if data.get("code") != 0:
            raise BilibiliError("API {}: {}".format(data.get("code"), data.get("message", "unknown")))
        return data.get("data") or {}

    def get_bytes(self, url, params=None):
        return self._request(url, params=params, binary=True)

    def get_wbi_keys(self):
        if self._wbi_keys:
            return self._wbi_keys
        data = self.get_json("https://api.bilibili.com/x/web-interface/nav")
        images = data["wbi_img"]
        self._wbi_keys = tuple(url.rsplit("/", 1)[-1].split(".", 1)[0] for url in (images["img_url"], images["sub_url"]))
        return self._wbi_keys
