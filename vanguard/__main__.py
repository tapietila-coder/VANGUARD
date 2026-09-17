"""CLI entry point: `python -m vanguard serve` runs the local API with uvicorn."""
import sys


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] != "serve":
        print("Usage: python -m vanguard serve")
        raise SystemExit(1)
    import uvicorn

    from .api.app import create_app

    uvicorn.run(create_app(), host="127.0.0.1", port=8788)


if __name__ == "__main__":
    main()
