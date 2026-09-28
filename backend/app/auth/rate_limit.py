import math
from collections import defaultdict, deque
from datetime import datetime, timedelta

from fastapi import HTTPException, status

from app.clock import utcnow


class FailureLimiter:
    """按键（IP、用户名等）统计一段时间内的失败次数，超过上限就暂时拒绝。

    计数只放在内存里：服务重启会清零，单进程部署下足够用。
    """

    def __init__(self, max_failures: int, window: timedelta):
        self.max_failures = max_failures
        self.window = window
        self._failures: dict[str, deque[datetime]] = defaultdict(deque)

    def _prune(self, key: str) -> deque[datetime]:
        failures = self._failures[key]
        cutoff = utcnow() - self.window
        while failures and failures[0] <= cutoff:
            failures.popleft()
        if not failures:
            del self._failures[key]
            return deque()
        return failures

    def check(self, *keys: str) -> None:
        """任意一个键超过上限就抛出 429。"""
        for key in keys:
            failures = self._prune(key)
            if len(failures) >= self.max_failures:
                wait = failures[0] + self.window - utcnow()
                minutes = max(1, math.ceil(wait.total_seconds() / 60))
                raise HTTPException(
                    status.HTTP_429_TOO_MANY_REQUESTS,
                    f"尝试次数过多，请 {minutes} 分钟后再试",
                )

    def record_failure(self, *keys: str) -> None:
        now = utcnow()
        for key in keys:
            self._failures[key].append(now)

    def reset(self, key: str) -> None:
        self._failures.pop(key, None)
