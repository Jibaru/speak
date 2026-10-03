import json

from speak.daemon.narrator import TranscriptFollower


def line(entry: dict) -> str:
    return json.dumps(entry) + "\n"


def assistant(*blocks: dict) -> dict:
    return {"type": "assistant", "message": {"content": list(blocks)}}


def test_partial_lines_wait_until_complete(tmp_path):
    transcript = tmp_path / "t.jsonl"
    transcript.write_text("")
    follower = TranscriptFollower(transcript)
    full = line(assistant({"type": "text", "text": "Hola."}))
    with transcript.open("a") as file:
        file.write(full[:10])
    assert follower.read_new_texts() == []
    with transcript.open("a") as file:
        file.write(full[10:])
    assert follower.read_new_texts() == ["Hola."]
    assert follower.read_new_texts() == []


def test_ignores_sidechains_tool_use_and_existing_content(tmp_path):
    transcript = tmp_path / "t.jsonl"
    transcript.write_text(line(assistant({"type": "text", "text": "Before watching."})))
    follower = TranscriptFollower(transcript)
    with transcript.open("a") as file:
        file.write(line({**assistant({"type": "text", "text": "Subagent."}), "isSidechain": True}))
        file.write(line(assistant({"type": "tool_use", "name": "Bash", "input": {}})))
        file.write("not json\n")
        file.write(line(assistant({"type": "text", "text": "  "}, {"type": "text", "text": "Mine."})))
    assert follower.read_new_texts() == ["Mine."]


def test_explicit_offset_and_missing_file(tmp_path):
    transcript = tmp_path / "t.jsonl"
    follower = TranscriptFollower(transcript, offset=0)
    assert follower.read_new_texts() == []
    transcript.write_text(line(assistant({"type": "text", "text": "Created later."})))
    assert follower.read_new_texts() == ["Created later."]
