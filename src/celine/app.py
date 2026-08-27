from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from celine.evaluation import BehaviorEvaluator, render_report
from celine.profile import ProfileError, ProfileInstaller
from celine.runtime import run_interactive, run_query
from celine_companion.presence import notify_desktop, presence_status


def _print_help() -> None:
    print(
        """Celine — agente independente

Uso:
  celine                         abre a TUI própria da Celine
  celine chat -q \"oi\"           executa uma conversa sem interface
  celine install [opções]        instala/atualiza somente ~/.celine
  celine doctor                  valida profile, runtime e assets
  celine evaluate [--live]       avalia personalidade e contratos
  celine presence status         mostra presença sem segredos
  celine presence notify ...     envia notificação desktop explícita
  celine home                    imprime o diretório isolado
  celine status                  mostra provider, modelo e sessão

A Celine não chama, importa ou depende do Hermes para executar.
"""
    )


def _run_install(args: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="celine install")
    parser.add_argument("--force-persona", action="store_true")
    parser.add_argument("--sync-auth", action="store_true", help="migração explícita de openai-codex de outro profile")
    parser.add_argument("--hermes-home", type=Path, help=argparse.SUPPRESS)
    ns = parser.parse_args(args)
    report = ProfileInstaller().install(
        force_persona=ns.force_persona,
        sync_auth=ns.sync_auth,
        source_hermes_home=ns.hermes_home,
    )
    print(report.render())
    return 0


def _run_presence(args: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="celine presence")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("status")
    notify = sub.add_parser("notify")
    notify.add_argument("--title", default="Celine")
    notify.add_argument("--message", required=True)
    ns = parser.parse_args(args)
    if ns.command in {None, "status"}:
        print(json.dumps(presence_status(ProfileInstaller().home), ensure_ascii=False, indent=2))
        return 0
    result = notify_desktop(ns.title, ns.message)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("success") else 1


def _run_evaluate(args: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="celine evaluate")
    parser.add_argument("--live", action="store_true")
    ns = parser.parse_args(args)
    installer = ProfileInstaller()
    installer.ensure_installed()
    evaluator = BehaviorEvaluator(installer.home)
    report = (
        evaluator.live(progress=lambda line: print(f"  {line}", flush=True))
        if ns.live
        else evaluator.static()
    )
    json_path, md_path = evaluator.save(report)
    print(render_report(report))
    print(f"Relatórios: {json_path} · {md_path}")
    return 0 if report["ok"] else 1


def _run_status() -> int:
    from celine.config import CelineConfig
    from celine.core.agent import CelineAgent

    config = CelineConfig.load()
    agent = CelineAgent(config)
    print(json.dumps({
        "identity": "Celine",
        "home": str(ProfileInstaller().home),
        "provider": config.model.provider,
        "model": config.model.default,
        "session": agent.active_session_id,
        "runtime": "celine-native",
    }, ensure_ascii=False, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    try:
        if not args or args == ["--tui"]:
            ProfileInstaller().ensure_installed()
            return run_interactive()
        if args[0] in {"-h", "--help"}:
            _print_help()
            return 0
        if args[0] == "install":
            return _run_install(args[1:])
        installer = ProfileInstaller()
        if args[0] == "home":
            print(installer.home)
            return 0
        if args[0] == "doctor":
            report = installer.doctor()
            print(report.render())
            return 0 if report.ok else 1
        if args[0] == "presence":
            return _run_presence(args[1:])
        if args[0] == "evaluate":
            return _run_evaluate(args[1:])
        if args[0] == "status":
            return _run_status()
        if args[0] == "chat":
            parser = argparse.ArgumentParser(prog="celine chat")
            parser.add_argument("-q", "--query", required=True)
            ns = parser.parse_args(args[1:])
            installer.ensure_installed()
            return run_query(ns.query)
        raise ProfileError(f"Comando desconhecido: {args[0]}. Use `celine --help`.")
    except (ProfileError, RuntimeError, ValueError) as exc:
        print(f"Celine não conseguiu iniciar: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
