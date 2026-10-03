import argparse
import json
import logging
import sys

from speak.client import DaemonClient
from speak.paths import Paths
from speak.settings import SettingsStore


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    paths = Paths.from_env()
    return args.run(args, paths) or 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="speak", description="Local voice output for Claude Code")
    commands = parser.add_subparsers(required=True)

    daemon = commands.add_parser("daemon", help="run the voice daemon in the foreground")
    daemon.set_defaults(run=_run_daemon)

    hook = commands.add_parser("hook", help="handle a Claude Code hook event read from stdin")
    hook.add_argument("event")
    hook.set_defaults(run=_run_hook)

    say = commands.add_parser("say", help="speak text (or stdin)")
    say.add_argument("text", nargs="*")
    say.add_argument("--mode", choices=["brief", "full"], default="full")
    say.set_defaults(run=_run_say)

    stop = commands.add_parser("stop", help="stop speaking")
    stop.set_defaults(run=lambda _args, paths: _print(DaemonClient(paths).request({"op": "stop", "source": "cli"})))

    status = commands.add_parser("status", help="show daemon status")
    status.set_defaults(run=lambda _args, paths: _print(DaemonClient(paths).request({"op": "status"})))

    shutdown = commands.add_parser("shutdown", help="stop the daemon")
    shutdown.set_defaults(run=lambda _args, paths: _print(DaemonClient(paths).request({"op": "shutdown"})))

    command = commands.add_parser("command", help="run a /speak command")
    command.add_argument("args", nargs="*")
    command.add_argument("--session")
    command.set_defaults(run=_run_command)

    setup = commands.add_parser("setup", help="download and warm up the voice model")
    setup.set_defaults(run=_run_setup)
    return parser


def _run_daemon(_args, paths: Paths) -> None:
    import asyncio

    from speak.daemon.engines import SAMPLE_RATE, EngineManager
    from speak.daemon.helper import Helper
    from speak.daemon.player import StreamPlayer
    from speak.daemon.server import Daemon

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    daemon = Daemon(paths, EngineManager(paths), StreamPlayer(SAMPLE_RATE), Helper(paths))
    asyncio.run(daemon.run())


def _run_hook(args, paths: Paths) -> None:
    from speak.hooks import HookHandler

    try:
        payload = json.loads(sys.stdin.read() or "{}")
        output = HookHandler(SettingsStore(paths), DaemonClient(paths)).handle(args.event, payload)
    except Exception as error:
        print(f"speak: {args.event} hook failed: {error}", file=sys.stderr)
        return
    if output:
        print(json.dumps(output))


def _run_say(args, paths: Paths) -> int:
    text = " ".join(args.text) or sys.stdin.read()
    response = DaemonClient(paths).send({"op": "speak", "text": text, "mode": args.mode}, start_daemon=True)
    _print(response)
    return 0 if response else 1


def _run_command(args, paths: Paths) -> None:
    from speak.commands import CommandRunner

    print(CommandRunner(SettingsStore(paths), DaemonClient(paths)).run(args.args, args.session))


def _run_setup(_args, paths: Paths) -> None:
    from speak.daemon.engines import KokoroEngine

    print("speak: downloading and warming up the voice model...", flush=True)
    engine = KokoroEngine(paths)
    engine.load()
    engine.warm(SettingsStore(paths).load())
    print("speak: ready")


def _print(response: dict | None) -> None:
    print(json.dumps(response) if response is not None else "speak: daemon is not running")
