import logging
import threading
from collections.abc import Callable

import numpy as np

from speak.engines.base import Engine, LoadableEngine
from speak.settings import Settings

log = logging.getLogger(__name__)


class EngineManager:
    def __init__(self, create_primary: Callable[[], LoadableEngine], fallback: Engine | None):
        self._create_primary = create_primary
        self._fallback = fallback
        self._primary: Engine | None = None
        self._ready = threading.Event()
        self._loading = threading.Event()

    @property
    def current(self) -> Engine | None:
        return self._primary or self._fallback

    def load_in_background(self, settings: Settings) -> None:
        if self._loading.is_set():
            return
        self._loading.set()
        threading.Thread(target=self._load, args=(settings,), name="engine-loader", daemon=True).start()

    def synthesize(self, text: str, lang: str, settings: Settings) -> np.ndarray:
        if self._primary is None and self._fallback is None:
            self._ready.wait()
        engine = self.current
        if engine is None:
            raise RuntimeError("no speech engine is available")
        try:
            return engine.synthesize(text, lang, settings)
        except Exception:
            if engine is self._fallback or self._fallback is None:
                raise
            log.exception("%s failed, falling back to %s", engine.name, self._fallback.name)
            return self._fallback.synthesize(text, lang, settings)

    def _load(self, settings: Settings) -> None:
        try:
            engine = self._create_primary()
            engine.load()
            engine.warm(settings)
            self._primary = engine
            log.info("%s engine ready", engine.name)
        except Exception:
            log.exception("primary engine failed to load")
        finally:
            self._ready.set()
