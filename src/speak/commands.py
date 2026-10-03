import re

from speak.client import DaemonClient
from speak.settings import Level, SettingsStore

COMMAND = re.compile(r"^\s*/(?:speak:)?speak(?:\s+(?P<args>.*))?\s*$", re.DOTALL)
MIN_RATE, MAX_RATE = 0.5, 2.0

USAGE = """Usage:
  /speak                         show status
  /speak off|brief|full|narrate  set the level for this session
  /speak default <level>         set the default level for new sessions
  /speak rate <0.5-2.0>          set the speaking rate
  /speak voice <lang> <voice>    set the Kokoro voice for a language (e.g. es ef_dora)
  /speak engine <name>           auto, kokoro-mlx (Apple Silicon) or kokoro-onnx
  /speak stop                    stop speaking
  /speak test                    say a short sample"""

ENGINES = ("auto", "kokoro-mlx", "kokoro-onnx")
TEST_PHRASES = "Voice is working. La voz está funcionando."


def parse(prompt: str) -> list[str] | None:
    match = COMMAND.match(prompt)
    if match is None:
        return None
    return (match.group("args") or "").split()


class CommandRunner:
    def __init__(self, store: SettingsStore, client: DaemonClient):
        self._store = store
        self._client = client

    def run(self, args: list[str], session_id: str | None) -> str:
        if not args:
            return self._status(session_id)
        command, *rest = args
        command = command.lower()
        if command in Level.__members__.values():
            return self._set_session_level(session_id, Level(command))
        handlers = {
            "default": self._set_default_level,
            "rate": self._set_rate,
            "voice": self._set_voice,
            "engine": self._set_engine,
            "stop": lambda _rest: self._stop(),
            "test": lambda _rest: self._test(session_id),
        }
        handler = handlers.get(command)
        return handler(rest) if handler else USAGE

    def _status(self, session_id: str | None) -> str:
        settings = self._store.load()
        level = self._store.effective_level(session_id)
        status = self._client.request({"op": "status"})
        daemon = f"running ({status['engine']})" if status else "not running"
        return f"speak: level {level} (default {settings.level}), rate {settings.rate}, daemon {daemon}"

    def _set_session_level(self, session_id: str | None, level: Level) -> str:
        if session_id is None:
            return self._set_default_level([level])
        self._store.set_session_level(session_id, level)
        if level is Level.OFF:
            self._client.request({"op": "stop"})
            self._client.request({"op": "unwatch", "session": session_id})
        else:
            self._client.ensure_running()
        return f"speak: level set to {level} for this session"

    def _set_default_level(self, rest: list[str]) -> str:
        if not rest or rest[0] not in Level.__members__.values():
            return USAGE
        self._store.update(level=Level(rest[0]))
        return f"speak: default level set to {rest[0]}"

    def _set_rate(self, rest: list[str]) -> str:
        try:
            rate = float(rest[0])
        except (IndexError, ValueError):
            return USAGE
        if not MIN_RATE <= rate <= MAX_RATE:
            return f"speak: rate must be between {MIN_RATE} and {MAX_RATE}"
        self._store.update(rate=rate)
        return f"speak: rate set to {rate}"

    def _set_voice(self, rest: list[str]) -> str:
        if len(rest) != 2:
            return USAGE
        lang, voice = rest
        voices = {**self._store.load().voices, lang: voice}
        self._store.update(voices=voices)
        return f"speak: {lang} voice set to {voice}"

    def _set_engine(self, rest: list[str]) -> str:
        if len(rest) != 1 or rest[0] not in ENGINES:
            return f"speak: engine must be one of {', '.join(ENGINES)}"
        self._store.update(engine=rest[0])
        self._client.request({"op": "shutdown"})
        return f"speak: engine set to {rest[0]}, it loads on the next reply"

    def _stop(self) -> str:
        self._client.request({"op": "stop", "source": "command"})
        return "speak: stopped"

    def _test(self, session_id: str | None) -> str:
        response = self._client.send({"op": "speak", "text": TEST_PHRASES, "session": session_id}, start_daemon=True)
        return "speak: speaking a sample" if response else "speak: daemon did not start, see ~/.cache/speak/daemon.log"
