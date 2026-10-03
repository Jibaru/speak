import asyncio
import json

import pytest

from speak.client import DaemonClient
from speak.daemon.server import Daemon
from speak.settings import SettingsStore
from tests.conftest import FakeEngine, FakeEngines


async def wait_for(condition, timeout=2.0):
    deadline = asyncio.get_running_loop().time() + timeout
    while not condition():
        if asyncio.get_running_loop().time() > deadline:
            raise AssertionError("condition not met in time")
        await asyncio.sleep(0.01)


@pytest.fixture
async def running(paths, fake_engines, fake_player):
    daemon = Daemon(paths, fake_engines, fake_player)
    task = asyncio.create_task(daemon.run())
    await wait_for(paths.socket.exists)
    yield daemon, fake_engines.engine, fake_player
    daemon.request_shutdown()
    await asyncio.wait_for(task, 2)


async def request(paths, message):
    return await asyncio.to_thread(DaemonClient(paths).request, message)


async def test_speak_over_socket_synthesizes_each_sentence(paths, running):
    _, engine, player = running
    response = await request(paths, {"op": "speak", "text": "Listo, ya está. All the tests are green now.", "mode": "full"})
    assert response == {"ok": True, "segments": 2}
    await wait_for(lambda: len(player.played) == 2)
    assert engine.spoken == [("Listo, ya está.", "es"), ("All the tests are green now.", "en")]


async def test_brief_mode_speaks_only_summary(paths, running):
    _, engine, _ = running
    await request(paths, {"op": "speak", "text": "Arreglé el error.\n\n## Detalles\nMucho texto.", "mode": "brief"})
    await wait_for(lambda: engine.spoken)
    await asyncio.sleep(0.05)
    assert engine.spoken == [("Arreglé el error.", "es")]


async def test_stop_clears_player_and_pending_segments(paths, fake_player):
    engines = FakeEngines(FakeEngine(delay=0.05))
    daemon = Daemon(paths, engines, fake_player)
    task = asyncio.create_task(daemon.run())
    await wait_for(paths.socket.exists)
    text = " ".join(f"Sentence number {index} is here." for index in range(10))
    await request(paths, {"op": "speak", "text": text})
    await wait_for(lambda: engines.engine.spoken)
    await request(paths, {"op": "stop"})
    await asyncio.sleep(0.2)
    assert fake_player.cleared >= 1
    assert len(engines.engine.spoken) < 10
    daemon.request_shutdown()
    await asyncio.wait_for(task, 2)


async def test_status_reports_engine(paths, running):
    status = await request(paths, {"op": "status"})
    assert status["ok"] and status["engine"] == "fake" and status["speaking"] is False


async def test_project_prefix_when_several_projects_are_active(paths, running):
    _, engine, _ = running
    await request(paths, {"op": "ping", "session": "a", "project": "alpha"})
    await request(paths, {"op": "speak", "text": "Done with that.", "session": "b", "project": "beta"})
    await wait_for(lambda: len(engine.spoken) == 2)
    assert engine.spoken[0][0] == "beta"


async def test_narrate_reads_new_assistant_text_blocks(paths, running, tmp_path):
    _, engine, _ = running
    transcript = tmp_path / "session.jsonl"
    transcript.write_text(json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "Old text."}]}}) + "\n")
    await request(paths, {"op": "watch", "session": "s", "transcript": str(transcript)})

    def append(entry):
        with transcript.open("a") as file:
            file.write(json.dumps(entry) + "\n")

    append({"type": "assistant", "message": {"content": [{"type": "thinking", "thinking": "hmm"}]}})
    append({"type": "assistant", "message": {"content": [{"type": "text", "text": "Let me check the file."}]}})
    append({"type": "user", "message": {"content": [{"type": "tool_result", "content": "x"}]}})
    await wait_for(lambda: engine.spoken)
    append({"type": "assistant", "message": {"content": [{"type": "text", "text": "All good."}]}})
    await request(paths, {"op": "finish", "session": "s"})
    await wait_for(lambda: len(engine.spoken) == 2)
    assert [text for text, _ in engine.spoken] == ["Let me check the file.", "All good."]


async def test_second_daemon_exits_when_one_is_running(paths, running, fake_engines, fake_player):
    second = Daemon(paths, fake_engines, fake_player)
    await asyncio.wait_for(second.run(), 1)


async def test_idle_daemon_shuts_down(paths, fake_engines, fake_player, monkeypatch):
    SettingsStore(paths).update(idle_minutes=0)
    monkeypatch.setattr("speak.daemon.server.HOUSEKEEPING_SECONDS", 0.05)
    daemon = Daemon(paths, fake_engines, fake_player)
    await asyncio.wait_for(daemon.run(), 2)
    assert not paths.socket.exists()
    assert fake_player.closed


async def test_unknown_op(paths, running):
    assert (await request(paths, {"op": "nope"}))["ok"] is False


async def test_interrupt_in_transcript_stops_narration(paths, running, tmp_path):
    _, _, player = running
    transcript = tmp_path / "session.jsonl"
    transcript.write_text("")
    await request(paths, {"op": "watch", "session": "s", "transcript": str(transcript)})
    cleared_before = player.cleared
    with transcript.open("a") as file:
        file.write(json.dumps({"type": "user", "message": {"content": [{"type": "text", "text": "[Request interrupted by user for tool use]"}]}}) + "\n")
    await wait_for(lambda: player.cleared > cleared_before)
    status = await request(paths, {"op": "status"})
    assert status["speaking"] is False
