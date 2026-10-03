from pathlib import Path

from speak import commands
from speak.client import DaemonClient
from speak.settings import Level, SettingsStore

INSTRUCTIONS = {
    Level.BRIEF: (
        "Voice mode (brief) is on: a short summary of your final reply will be spoken aloud. "
        "Begin your final reply with a one or two sentence spoken summary of the outcome as its own "
        "first paragraph: plain conversational prose in the user's language, with no markdown, code, "
        "file paths or lists. Then continue normally."
    ),
    Level.FULL: (
        "Voice mode (full) is on: your final reply will be read aloud. Prefer short prose paragraphs; "
        "code blocks and tables are skipped when spoken."
    ),
    Level.NARRATE: (
        "Voice mode (narrate) is on: everything you write is read aloud as you go. Before tool calls, "
        "a short sentence saying what you are about to do is welcome. Prefer short prose paragraphs; "
        "code blocks and tables are skipped when spoken."
    ),
}


class HookHandler:
    def __init__(self, store: SettingsStore, client: DaemonClient):
        self._store = store
        self._client = client
        self._commands = commands.CommandRunner(store, client)

    def handle(self, event: str, payload: dict) -> dict | None:
        handler = {
            "SessionStart": self._session_start,
            "UserPromptSubmit": self._user_prompt_submit,
            "Stop": self._stop,
            "Notification": self._notification,
            "SessionEnd": self._session_end,
        }.get(event)
        return handler(payload) if handler else None

    def _session_start(self, payload: dict) -> None:
        if self._level(payload) is not Level.OFF:
            self._client.ensure_running()

    def _user_prompt_submit(self, payload: dict) -> dict | None:
        args = commands.parse(payload.get("prompt", ""))
        if args is not None:
            return {"decision": "block", "reason": self._commands.run(args, payload.get("session_id"))}

        self._client.request({"op": "stop", "source": "prompt"})
        level = self._level(payload)
        if level is Level.OFF:
            return None
        if level is Level.NARRATE:
            self._client.send(self._watch_message(payload), start_daemon=True)
        else:
            self._client.send(self._identify(payload, {"op": "ping"}), start_daemon=True)
        return {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": INSTRUCTIONS[level]}}

    def _stop(self, payload: dict) -> None:
        level = self._level(payload)
        if level is Level.OFF:
            return
        if level is Level.NARRATE:
            self._client.send(self._identify(payload, {"op": "finish"}), start_daemon=True)
            return
        text = payload.get("last_assistant_message") or ""
        if text.strip():
            message = {"op": "speak", "text": text, "mode": "brief" if level is Level.BRIEF else "full"}
            self._client.send(self._identify(payload, message), start_daemon=True)

    def _notification(self, payload: dict) -> None:
        if self._level(payload) is not Level.NARRATE or not _is_attention_request(payload):
            return
        message = {"op": "speak", "text": payload.get("message", ""), "preempt": False}
        self._client.send(self._identify(payload, message), start_daemon=True)

    def _session_end(self, payload: dict) -> None:
        session = payload.get("session_id")
        if session:
            self._store.clear_session(session)
            self._client.request({"op": "unwatch", "session": session})

    def _level(self, payload: dict) -> Level:
        return self._store.effective_level(payload.get("session_id"))

    def _watch_message(self, payload: dict) -> dict:
        transcript = Path(payload.get("transcript_path", ""))
        offset = transcript.stat().st_size if transcript.is_file() else 0
        return self._identify(payload, {"op": "watch", "transcript": str(transcript), "offset": offset})

    @staticmethod
    def _identify(payload: dict, message: dict) -> dict:
        cwd = payload.get("cwd") or ""
        return {**message, "session": payload.get("session_id"), "project": Path(cwd).name or None}


def _is_attention_request(payload: dict) -> bool:
    kind = payload.get("notification_type")
    if kind:
        return kind == "permission_prompt"
    return "permission" in payload.get("message", "").lower()
