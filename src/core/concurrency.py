"""Control de concurrencia e idempotencia para evitar peticiones simultáneas a Binance P2P."""

import logging
import threading
import time
from typing import Optional

logger = logging.getLogger("concurrency")


class ConcurrencyLockError(RuntimeError):
    """Lanzada cuando una tarea intenta ejecutarse mientras otra ya está en curso."""


class SyncLockManager:
    """Gestor singleton de exclusión mutua para peticiones de red hacia Binance."""
    _instance: Optional["SyncLockManager"] = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._is_locked = False
                cls._instance._lock_timestamp = 0.0
                cls._instance._current_task = ""
            return cls._instance

    def acquire(self, task_name: str = "sync_orders", max_duration_seconds: float = 60.0) -> bool:
        """Intenta adquirir el bloqueo. Si hay un bloqueo huérfano de más de max_duration_seconds, lo libera."""
        with self._lock:
            now = time.time()
            # Auto-recuperación de bloqueos muertos
            if self._is_locked and (now - self._lock_timestamp) > max_duration_seconds:
                logger.warning(
                    f"Liberando bloqueo expirado de '{self._current_task}' que duró más de {max_duration_seconds}s."
                )
                self._is_locked = False

            if self._is_locked:
                return False

            self._is_locked = True
            self._lock_timestamp = now
            self._current_task = task_name
            return True

    def release(self) -> None:
        """Libera el bloqueo activo."""
        with self._lock:
            self._is_locked = False
            self._current_task = ""

    @property
    def is_locked(self) -> bool:
        with self._lock:
            return self._is_locked

    @property
    def current_task(self) -> str:
        with self._lock:
            return self._current_task
