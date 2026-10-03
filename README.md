# speak

Local, low-latency voice output for Claude Code.

`speak` is a Claude Code plugin that reads Claude's replies aloud with an on-device TTS engine
([Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M) on [MLX](https://github.com/ml-explore/mlx)).
Text output is unchanged, the voice starts within ~100 ms of the reply, and it can be interrupted at any time.
Nothing leaves your machine.

macOS on Apple Silicon only.

## Install

```
/plugin marketplace add Jibaru/speak
/plugin install speak@jibaru
```

The first session installs everything it needs into `~/.cache/speak` in the background (an isolated
Python, the locked dependencies and the ~350 MB voice model). Nothing is installed globally and no
Homebrew or system Python is required. Until it is ready, replies are spoken with macOS `say`.

To install ahead of time, run the launcher once:

```
~/.claude/plugins/cache/jibaru/speak/*/bin/speak install
```

## Levels

| Level | What is spoken |
|---|---|
| `off` | Nothing |
| `brief` (default) | A one or two sentence summary that Claude writes at the top of its final reply |
| `full` | The whole final reply; code blocks, tables and links are replaced by a short phrase |
| `narrate` | Everything Claude writes as it works, plus permission prompts |

## Commands

```
/speak                         show status
/speak off|brief|full|narrate  set the level for this session
/speak default <level>         set the default level for new sessions
/speak rate <0.5-2.0>          set the speaking rate (default 1.15)
/speak voice <lang> <voice>    set the Kokoro voice for a language, e.g. /speak voice es em_alex
/speak stop                    stop speaking
/speak test                    say a short sample
```

`/speak` is handled by a hook, so it never costs a model turn.

## Interrupting

Speech stops when you:

- send a new prompt,
- press **⌥ Esc** anywhere (global hotkey, no accessibility permission needed),
- start dictating with `/voice` or any app opens the microphone,
- press **Esc** to interrupt Claude while it is narrating (detected from the session transcript).

## Languages

Each sentence is spoken in its own language (English, Spanish, French, Italian, Portuguese), so mixed
replies switch voices naturally. Tech jargon inside Spanish sentences is respelled so it sounds right
(`deploy`, `hook`, `TypeScript`...). Add your own respellings in `~/.config/speak/lexicon.json`:

```json
{ "es": { "Kubernetes": "cubernetis" } }
```

## Configuration

`~/.config/speak/config.json`:

```json
{
  "level": "brief",
  "rate": 1.15,
  "voices": { "en": "af_heart", "es": "ef_dora" },
  "hotkey": "option+escape",
  "stop_on_mic": true,
  "idle_minutes": 30
}
```

Available Kokoro voices are listed in the
[model card](https://huggingface.co/hexgrad/Kokoro-82M/blob/main/VOICES.md).

## How it works

- **Hooks, not tools.** `UserPromptSubmit`, `Stop`, `Notification` and `SessionStart` hooks drive the
  voice deterministically; Claude never has to remember to speak.
- **A warm daemon.** A local daemon keeps the model in memory, owns a single audio queue (the newest
  reply preempts older ones, across sessions) and exits after 30 idle minutes.
- **Streaming narration.** In `narrate` mode the daemon tails the session transcript and speaks each
  text block as soon as it is written.
- **A tiny native helper** (`helper/main.swift`) registers the global hotkey and watches the
  microphone through CoreAudio.

## Development

```
uv sync
uv run pytest
helper/build.sh          # rebuild bin/speak-helper
claude --plugin-dir .    # try the plugin from this checkout
```

Logs: `~/.cache/speak/daemon.log`. Status: `bin/speak status`.
