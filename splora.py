import argparse
from collections.abc import Callable

from src.boot import Boot
from src.command import Command
from src.explore import Explore
from src.frame import run
from src.report import Report
from src.terminal import OutputConfig, output_config

_CommandFactory = Callable[[argparse.Namespace, OutputConfig], Command]
_COMMANDS: dict[str, _CommandFactory] = {"explore": Explore, "report": Report, "boot": Boot}


def _global_flags() -> argparse.ArgumentParser:
    """Build the parser holding the flags every subcommand accepts after its own name."""
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--trim-output",
        action="store_true",
        dest="trim_output",
        help="Print only the result summary, without the banner or the next-step advice.",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        dest="no_color",
        help="Disable coloured output.",
    )
    return parser


def main() -> int:
    """Parse command-line arguments, run the requested command, and return its exit code."""
    common = _global_flags()
    parser = argparse.ArgumentParser(
        prog="splora",
        description="A locally hosted, cross-platform file system data visualization tool.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # ── explore ────────────────────────────────────────────────────────────
    ep = sub.add_parser(
        "explore", help="Traverse a file system and record its structure.", parents=[common]
    )
    ep.add_argument("path", help="Root path to explore.")
    ep.add_argument(
        "--name",
        help="Name for this run (used as filename and report title). Defaults to root folder name.",
    )
    ep.add_argument(
        "--depth",
        type=int,
        default=0,
        metavar="N",
        help="Max subdirectory depth. 0 = unlimited (default).",
    )
    ep.add_argument(
        "--max-files", type=int, dest="max_files", metavar="N", help="Stop after visiting N files."
    )
    ep.add_argument("--timeout", type=float, metavar="SECONDS", help="Stop after SECONDS elapsed.")
    ep.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="NAME",
        help="Exclude directories with this exact name. Repeatable.",
    )
    ep.add_argument(
        "--no-default-excludes",
        action="store_true",
        dest="no_default_excludes",
        help="Disable the built-in default exclude list.",
    )

    # ── report ─────────────────────────────────────────────────────────────
    rp = sub.add_parser(
        "report", help="Generate an HTML report from an exploration run.", parents=[common]
    )
    rp.add_argument("--name", help="Run name to use (default: last modified).")

    # ── boot ───────────────────────────────────────────────────────────────
    bp = sub.add_parser("boot", help="Open a generated report in the browser.", parents=[common])
    bp.add_argument("--name", help="Report name to open (default: last generated).")

    args = parser.parse_args()
    config = output_config(args)
    return run(_COMMANDS[args.command](args, config), config)


if __name__ == "__main__":
    raise SystemExit(main())
