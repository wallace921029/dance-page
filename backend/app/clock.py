from datetime import UTC, datetime, timedelta

# 仅供测试"快进时间"使用，正常运行时始终为 0
offset = timedelta(0)


def utcnow() -> datetime:
    """当前 UTC 时间。所有业务代码都经由这里取时间。"""
    return datetime.now(UTC) + offset
