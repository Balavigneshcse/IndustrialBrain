"""Celery application: Redis broker, document-processing tasks and a worker heartbeat.

Run a worker:  python -m celery -A server.app.workers.celery_app worker --loglevel=INFO
(on Windows add --pool=threads). Without REDIS_URL, tasks run inline in the API process.
"""
import threading
import time

from celery import Celery
from celery.signals import worker_ready, worker_shutting_down

from ..core.config import get_settings

settings = get_settings()
HEARTBEAT_KEY = "indusmind:worker:heartbeat"

celery_app = Celery("indusmind", broker=settings.redis_url or "memory://", include=["server.app.workers.tasks"])
celery_app.conf.update(
    task_always_eager=settings.jobs_eager,
    task_eager_propagates=True,
    task_ignore_result=True,
    task_acks_late=True,              # a crashed worker leaves the task in the queue
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,     # long CPU-bound tasks: take one at a time
    task_time_limit=900,
    task_soft_time_limit=840,
    task_default_queue="indusmind",
    broker_connection_retry_on_startup=True,
    worker_hijack_root_logger=False,
    worker_redirect_stdouts_level="INFO",  # the app's structured logs are info, not warnings
)

_stop = threading.Event()


def _heartbeat() -> None:
    import redis

    client = redis.Redis.from_url(settings.redis_url)
    while not _stop.is_set():
        try:
            client.set(HEARTBEAT_KEY, str(time.time()), ex=30)
        except redis.RedisError:
            pass
        _stop.wait(10)


@worker_ready.connect
def _start_heartbeat(**_) -> None:
    if settings.redis_url:
        threading.Thread(target=_heartbeat, name="heartbeat", daemon=True).start()


@worker_shutting_down.connect
def _stop_heartbeat(**_) -> None:
    _stop.set()
