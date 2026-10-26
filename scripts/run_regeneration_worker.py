from __future__ import annotations

import argparse
import asyncio

from app.domains.lifecycle.worker_process import run_regeneration_worker


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the AIrchitect regeneration worker")
    parser.add_argument("--worker-id", default=None)
    parser.add_argument("--poll-interval", type=float, default=1.0)
    args = parser.parse_args()
    asyncio.run(
        run_regeneration_worker(
            worker_id=args.worker_id,
            poll_interval=args.poll_interval,
        )
    )


if __name__ == "__main__":
    main()
