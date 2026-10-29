"""Standalone worker entry point for Amazon Kinesis CloudFront log consumption.

Usage:
    python -m app.workers.kinesis_worker
"""

from __future__ import annotations

import logging
import signal
import sys

from app.aws.kinesis_consumer import kinesis_consumer
from app.core.config import get_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("sentrix.kinesis_worker")


def main() -> None:
    settings = get_settings()
    logger.info("Starting SENTRIX CloudFront Kinesis Worker...")
    logger.info("Stream Name: %s", settings.aws_kinesis_stream_name)
    logger.info("AWS Region: %s", settings.aws_region)
    logger.info("Batch Size: %d", settings.aws_kinesis_batch_size)
    logger.info("Poll Interval: %.1fs", settings.aws_kinesis_poll_interval_seconds)

    def shutdown_handler(signum: int, frame: object) -> None:
        logger.info(
            "Received signal %s, initiating graceful worker shutdown...", signum
        )
        kinesis_consumer.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    try:
        kinesis_consumer.run_worker_loop()
    except Exception:
        logger.exception("Unhandled worker exception")
        sys.exit(1)


if __name__ == "__main__":
    main()
