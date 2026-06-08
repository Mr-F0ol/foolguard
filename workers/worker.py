"""Entrypoint do Build Worker.

Rodar localmente:
    python -m workers.worker

Via docker-compose, este script é o CMD do container 'worker'.
O worker fica escutando a fila "builds" no Redis e executa as tarefas
conforme chegam. Se o Redis estiver indisponível ao iniciar, o worker
tenta reconectar automaticamente (retry padrão do RQ).
"""

from redis import Redis
from rq import Queue, Worker

from app.core.config import settings

if __name__ == "__main__":
    conn = Redis.from_url(settings.redis_url)
    queue = Queue("builds", connection=conn)
    worker = Worker([queue], connection=conn)
    print(f"[worker] Escutando fila 'builds' em {settings.redis_url}")
    worker.work()
