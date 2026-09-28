"""启动方式：python -m app.worker"""

import logging
import signal

from app.config import get_settings
from app.db import create_db_engine, create_session_factory
from app.worker.runner import Worker


def main() -> None:
    # 非交互 shell 的后台进程会继承"忽略 SIGINT"，Python 就不会抛 KeyboardInterrupt；
    # 恢复默认处理，watchfiles 重启或 dev.sh 停止时 Worker 才能立即退出
    signal.signal(signal.SIGINT, signal.default_int_handler)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = get_settings()
    engine = create_db_engine(settings.database_url)
    worker = Worker(settings, create_session_factory(engine))
    try:
        worker.run_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
