"""Top-level `kira-hq` CLI dispatcher."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from kira_hq.cli import add_project, archive_project
from kira_hq.doctor import doctor_report, format_doctor_json, format_doctor_text
from kira_hq.hermes_bridge import BridgeError, BridgeRequest, invoke_bridge
from kira_hq.telegram.bridge import (
    TelegramBotClient,
    TelegramBridge,
    TelegramBridgeConfig,
    TelegramBridgeError,
)
from kira_hq.task_store import (
    TaskNotFoundError,
    TaskValidationError,
    add_task,
    list_tasks,
    set_status,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kira-hq",
        description="Kira-HQ command line interface.",
    )
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("add-project", parents=[add_project._build_parser()], add_help=False)
    subparsers.add_parser("archive-project", parents=[archive_project._build_parser()], add_help=False)

    list_parser = subparsers.add_parser("list-tasks", help="List tasks from the shared task store.")
    list_parser.add_argument("--project-dir", default=".")
    list_parser.add_argument("--json", action="store_true", dest="as_json")
    list_parser.add_argument("--status")

    add_task_parser = subparsers.add_parser("add-task", help="Add a task via the shared lock-safe store.")
    add_task_parser.add_argument("title")
    add_task_parser.add_argument("--description", default="")
    add_task_parser.add_argument("--priority", default="medium")
    add_task_parser.add_argument("--depends-on", action="append", default=[])
    add_task_parser.add_argument("--project-dir", default=".")
    add_task_parser.add_argument("--json", action="store_true", dest="as_json")

    set_status_parser = subparsers.add_parser("set-status", help="Update task status via the shared lock-safe store.")
    set_status_parser.add_argument("task_id")
    set_status_parser.add_argument("status")
    set_status_parser.add_argument("--project-dir", default=".")
    set_status_parser.add_argument("--json", action="store_true", dest="as_json")

    doctor_parser = subparsers.add_parser("doctor", help="Run Claude/Hermes readiness checks.")
    doctor_parser.add_argument("--project-dir", default=".")
    doctor_parser.add_argument("--json", action="store_true", dest="as_json")

    bridge_parser = subparsers.add_parser(
        "delegate-worker",
        help="Shared Claude->Hermes(worker)->OpenRouter/Qwen bridge entrypoint.",
    )
    bridge_parser.add_argument("--task-id", required=True)
    bridge_parser.add_argument("--prompt", required=True)
    bridge_parser.add_argument("--project-dir", default=".")
    bridge_parser.add_argument("--handoff-out", required=True)
    bridge_parser.add_argument("--worker-command", default="hermes")
    bridge_parser.add_argument("--provider", default="openrouter")
    bridge_parser.add_argument("--model", default="qwen/qwen3-coder-30b-a3b-instruct")
    bridge_parser.add_argument("--track", default="B")
    bridge_parser.add_argument("--project-name")
    bridge_parser.add_argument("--global-pipeline-log")
    bridge_parser.add_argument("--json", action="store_true", dest="as_json")

    telegram_parser = subparsers.add_parser(
        "telegram-serve",
        help="Run the local Telegram Bot API long-poll bridge.",
    )
    telegram_parser.add_argument("--project-dir", default=".")
    telegram_parser.add_argument("--inbox-dir")
    telegram_parser.add_argument("--outbox-dir")
    telegram_parser.add_argument("--offset-path")
    telegram_parser.add_argument("--poll-timeout", type=int, default=30)
    telegram_parser.add_argument("--message-max-chars", type=int, default=4000)
    telegram_parser.add_argument("--outbox-ttl-seconds", type=int, default=3600)
    telegram_parser.add_argument("--once", action="store_true")
    return parser


def _json_dump(payload: object) -> None:
    print(json.dumps(payload, indent=2))


def _handle_list_tasks(args: argparse.Namespace) -> int:
    tag, tasks = list_tasks(args.project_dir)
    if args.status:
        tasks = [task for task in tasks if str(task.get("status")) == args.status]
    payload = {"tag": tag, "tasks": tasks}
    if args.as_json:
        _json_dump(payload)
    else:
        print(f"tag: {tag}")
        for task in tasks:
            print(f"- {task.get('id')}: [{task.get('status')}] {task.get('title')}")
    return 0


def _handle_add_task(args: argparse.Namespace) -> int:
    result = add_task(
        args.project_dir,
        title=args.title,
        description=args.description,
        priority=args.priority,
        dependencies=args.depends_on,
    )
    payload = {"tag": result.tag, "task": result.task}
    if args.as_json:
        _json_dump(payload)
    else:
        print(f"added task {result.task['id']} under tag {result.tag}: {result.task['title']}")
    return 0


def _handle_set_status(args: argparse.Namespace) -> int:
    result = set_status(args.project_dir, task_id=args.task_id, status=args.status)
    payload = {"tag": result.tag, "task": result.task}
    if args.as_json:
        _json_dump(payload)
    else:
        print(f"task {result.task['id']} -> {result.task['status']} (tag={result.tag})")
    return 0


def _handle_doctor(args: argparse.Namespace) -> int:
    report = doctor_report(args.project_dir)
    if args.as_json:
        print(format_doctor_json(report), end="")
    else:
        print(format_doctor_text(report))
    return 0 if report["ok"] else 1


def _handle_bridge(args: argparse.Namespace) -> int:
    request = BridgeRequest(
        task_id=str(args.task_id),
        prompt=args.prompt,
        project_dir=Path(args.project_dir).expanduser().resolve(),
        handoff_out=Path(args.handoff_out).expanduser().resolve(),
        worker_command=args.worker_command,
        provider=args.provider,
        model=args.model,
        track=args.track,
        project_name=args.project_name,
        global_pipeline_log=Path(args.global_pipeline_log).expanduser().resolve() if args.global_pipeline_log else None,
    )
    result = invoke_bridge(request)
    payload = {
        "command": result.command,
        "handoff_out": str(request.handoff_out),
        "handoff": result.handoff,
    }
    if args.as_json:
        _json_dump(payload)
    else:
        print(f"handoff written: {request.handoff_out}")
        print(json.dumps(result.handoff, indent=2))
    return 0


def _handle_telegram_serve(args: argparse.Namespace) -> int:
    project_dir = Path(args.project_dir).expanduser().resolve()
    config = TelegramBridgeConfig.from_sources(
        project_dir=project_dir,
        inbox_dir=Path(args.inbox_dir).expanduser() if args.inbox_dir else None,
        outbox_dir=Path(args.outbox_dir).expanduser() if args.outbox_dir else None,
        offset_path=Path(args.offset_path).expanduser() if args.offset_path else None,
        poll_timeout_s=args.poll_timeout,
        message_max_chars=args.message_max_chars,
        outbox_ttl_seconds=args.outbox_ttl_seconds,
    )
    bridge = TelegramBridge(
        config,
        telegram_client=TelegramBotClient(config.bot_token),
        project_dir=project_dir,
    )
    bridge.serve_forever(max_iterations=1 if args.once else None)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        _build_parser().print_help()
        return 0
    try:
        if args[0] == "add-project":
            return add_project.main(args[1:])
        if args[0] == "archive-project":
            return archive_project.main(args[1:])

        parsed = _build_parser().parse_args(args)
        command = parsed.command
        if command == "list-tasks":
            return _handle_list_tasks(parsed)
        if command == "add-task":
            return _handle_add_task(parsed)
        if command == "set-status":
            return _handle_set_status(parsed)
        if command == "doctor":
            return _handle_doctor(parsed)
        if command == "delegate-worker":
            return _handle_bridge(parsed)
        if command == "telegram-serve":
            return _handle_telegram_serve(parsed)
    except SystemExit as exc:
        code = exc.code
        return code if isinstance(code, int) else 0
    except (TaskValidationError, TaskNotFoundError, BridgeError, TelegramBridgeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if args[0] in {"-h", "--help"}:
        _build_parser().print_help()
        return 0
    raise SystemExit(f"unknown command: {args[0]}")


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
