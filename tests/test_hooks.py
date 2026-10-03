import pytest

from speak import commands
from speak.hooks import INSTRUCTIONS, HookHandler
from speak.settings import Level, SettingsStore


class RecordingClient:
    def __init__(self, running=True):
        self.requests: list[dict] = []
        self.sent: list[dict] = []
        self.spawned = 0
        self.running = running

    def request(self, message, timeout=0.5):
        self.requests.append(message)
        return {"ok": True, "engine": "fake"} if self.running else None

    def send(self, message, start_daemon=False):
        self.sent.append(message)
        return {"ok": True}

    def ensure_running(self):
        if not self.running:
            self.spawned += 1
        return self.running


@pytest.fixture
def store(paths):
    return SettingsStore(paths)


@pytest.fixture
def client():
    return RecordingClient()


@pytest.fixture
def handler(store, client):
    return HookHandler(store, client)


PAYLOAD = {"session_id": "s1", "cwd": "/work/myproject", "transcript_path": "/nonexistent.jsonl"}


def test_prompt_stops_audio_and_injects_brief_instruction(handler, client):
    output = handler.handle("UserPromptSubmit", {**PAYLOAD, "prompt": "fix the bug"})
    assert client.requests[0] == {"op": "stop", "source": "prompt"}
    assert output["hookSpecificOutput"]["additionalContext"] == INSTRUCTIONS[Level.BRIEF]


def test_prompt_with_voice_off_only_stops(handler, client, store):
    store.update(level=Level.OFF)
    assert handler.handle("UserPromptSubmit", {**PAYLOAD, "prompt": "hi"}) is None
    assert client.sent == []


def test_narrate_prompt_starts_watching(handler, client, store):
    store.set_session_level("s1", Level.NARRATE)
    handler.handle("UserPromptSubmit", {**PAYLOAD, "prompt": "go"})
    assert client.sent[0]["op"] == "watch"
    assert client.sent[0]["session"] == "s1" and client.sent[0]["project"] == "myproject"


def test_speak_command_is_blocked_and_applied(handler, store):
    output = handler.handle("UserPromptSubmit", {**PAYLOAD, "prompt": "/speak full"})
    assert output == {"decision": "block", "reason": "speak: level set to full for this session"}
    assert store.session_level("s1") is Level.FULL
    assert store.load().level is Level.BRIEF


def test_stop_speaks_last_message_in_brief_mode(handler, client):
    handler.handle("Stop", {**PAYLOAD, "last_assistant_message": "Listo."})
    assert client.sent == [{"op": "speak", "text": "Listo.", "mode": "brief", "session": "s1", "project": "myproject"}]


def test_stop_in_narrate_mode_finishes_watch(handler, client, store):
    store.set_session_level("s1", Level.NARRATE)
    handler.handle("Stop", {**PAYLOAD, "last_assistant_message": "Listo."})
    assert client.sent == [{"op": "finish", "text": "Listo.", "session": "s1", "project": "myproject"}]


def test_stop_with_voice_off_is_silent(handler, client, store):
    store.set_session_level("s1", Level.OFF)
    handler.handle("Stop", {**PAYLOAD, "last_assistant_message": "Listo."})
    assert client.sent == []


def test_notification_spoken_only_for_permission_in_narrate(handler, client, store):
    handler.handle("Notification", {**PAYLOAD, "message": "Claude needs your permission to use Bash"})
    assert client.sent == []
    store.set_session_level("s1", Level.NARRATE)
    handler.handle("Notification", {**PAYLOAD, "message": "Claude is waiting for your input", "notification_type": "idle_prompt"})
    assert client.sent == []
    handler.handle("Notification", {**PAYLOAD, "message": "Claude needs your permission to use Bash"})
    assert client.sent[0]["op"] == "speak" and client.sent[0]["preempt"] is False


def test_session_start_spawns_daemon(store):
    client = RecordingClient(running=False)
    HookHandler(store, client).handle("SessionStart", PAYLOAD)
    assert client.spawned == 1


def test_session_end_clears_session_level(handler, store):
    store.set_session_level("s1", Level.FULL)
    handler.handle("SessionEnd", PAYLOAD)
    assert store.session_level("s1") is None


@pytest.mark.parametrize(
    ("prompt", "expected"),
    [("/speak", []), ("/speak full", ["full"]), ("/speak:speak rate 1.2", ["rate", "1.2"]), ("/speaker", None), ("speak full", None)],
)
def test_parse_command(prompt, expected):
    assert commands.parse(prompt) == expected


@pytest.mark.parametrize(
    ("args", "reply"),
    [
        (["default", "narrate"], "speak: default level set to narrate"),
        (["rate", "1.3"], "speak: rate set to 1.3"),
        (["rate", "9"], "speak: rate must be between 0.5 and 2.0"),
        (["voice", "es", "em_alex"], "speak: es voice set to em_alex"),
        (["bogus"], commands.USAGE),
    ],
)
def test_command_runner(store, client, args, reply):
    assert commands.CommandRunner(store, client).run(args, "s1") == reply


def test_command_status(store, client):
    assert commands.CommandRunner(store, client).run([], "s1") == (
        "speak: level brief (default brief), rate 1.15, daemon running (fake)"
    )


def test_command_settings_persist(store, client):
    runner = commands.CommandRunner(store, client)
    runner.run(["rate", "1.3"], "s1")
    runner.run(["voice", "es", "em_alex"], "s1")
    settings = store.load()
    assert settings.rate == 1.3 and settings.voices["es"] == "em_alex" and settings.voices["en"] == "af_heart"
