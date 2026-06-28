import argparse

from src.boot import boot
from src.explore import explore
from src.report import report


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="splora",
        description="A locally hosted, cross-platform file system data visualization tool.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # ── explore ────────────────────────────────────────────────────────────
    ep = sub.add_parser("explore", help="Traverse a file system and record its structure.")
    ep.add_argument("path", help="Root path to explore.")
    ep.add_argument("--name", help="Name for this run (used as filename and report title). Defaults to root folder name.")
    ep.add_argument("--depth", type=int, default=0, metavar="N", help="Max subdirectory depth. 0 = unlimited (default).")
    ep.add_argument("--max-files", type=int, dest="max_files", metavar="N", help="Stop after visiting N files.")
    ep.add_argument("--timeout", type=float, metavar="SECONDS", help="Stop after SECONDS elapsed.")
    ep.add_argument("--exclude", action="append", default=[], metavar="NAME", help="Exclude directories with this exact name. Repeatable.")
    ep.add_argument("--no-default-excludes", action="store_true", dest="no_default_excludes", help="Disable the built-in default exclude list.")

    # ── report ─────────────────────────────────────────────────────────────
    rp = sub.add_parser("report", help="Generate an HTML report from an exploration run.")
    rp.add_argument("--name", help="Run name to use (default: last modified).")

    # ── boot ───────────────────────────────────────────────────────────────
    bp = sub.add_parser("boot", help="Open a generated report in the browser.")
    bp.add_argument("--name", help="Report name to open (default: last generated).")

    args = parser.parse_args()

    if args.command == "explore":
        explore(args)
    elif args.command == "report":
        report(args)
    elif args.command == "boot":
        boot(args)


if __name__ == "__main__":
    main()
