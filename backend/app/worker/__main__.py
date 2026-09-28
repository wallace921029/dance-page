"""启动方式：python -m app.worker"""

import logging

from app.config import get_settings
from app.db import create_db_engine, create_session_factory
from app.worker.runner import Worker


def main() -> None:
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
