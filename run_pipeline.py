from __future__ import annotations

import argparse
import asyncio

from sisyphus.pipeline.build import audit, ingest, publish, run, transform


def main() -> None:
    parser = argparse.ArgumentParser(description="Constrói a base curada do Sisyphus")
    parser.add_argument(
        "stage",
        choices=("all", "ingest", "transform", "publish", "audit"),
        nargs="?",
        default="all",
    )
    stage = parser.parse_args().stage
    if stage == "all":
        result = run()
    elif stage == "ingest":
        result = {"snapshots": len(asyncio.run(ingest()))}
    elif stage == "transform":
        transform()
        result = {"transformed": 1}
    elif stage == "publish":
        publish()
        result = {"published": 1}
    else:
        result = audit()
    print(result)


if __name__ == "__main__":
    main()
