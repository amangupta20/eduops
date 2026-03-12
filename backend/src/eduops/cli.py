import argparse
import sys

import uvicorn


def main() -> int:
    parser = argparse.ArgumentParser(description="eduops CLI")
    subparsers = parser.add_subparsers(dest="command", required=True, help="Available commands")

    start_parser = subparsers.add_parser("start", help="Start the eduops server")
    start_parser.add_argument(
        "--port",
        type=int,
        default=7337,
        help="Port to run the server on (default: 7337)",
    )

    args = parser.parse_args()

    if args.command == "start":
        uvicorn.run("eduops.app:app", host="127.0.0.1", port=args.port)
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
