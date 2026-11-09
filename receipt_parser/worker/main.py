"""SQS long-polling loop for the receipt parser worker.

A message is deleted only after it was processed successfully. On failure it stays in the
queue: it becomes visible again after the visibility timeout and is redelivered, and after
`maxReceiveCount` attempts SQS moves it to the dead-letter queue. On the last attempt the
receipt is marked FAILED so the user sees an error instead of waiting forever.
"""

import logging
import os
import signal

import boto3

from worker.engine import DummyEngine
from worker.processor import mark_failed, process_message

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("worker")

_stop = False


def _request_stop(signum, _frame):
    # ECS sends SIGTERM on deploys/scale-in: finish the current message, then exit.
    global _stop
    logger.info("Signal %s received, stopping after the current message", signum)
    _stop = True


def run() -> None:
    queue_url = os.environ["QUEUE_URL"]
    region = os.environ["AWS_REGION"]
    max_receives = int(os.getenv("MAX_RECEIVE_COUNT", "3"))

    sqs = boto3.client("sqs", region_name=region)
    s3 = boto3.client("s3", region_name=region)
    table = boto3.resource("dynamodb", region_name=region).Table(os.environ["DYNAMODB_TABLE_NAME"])
    engine = DummyEngine()

    signal.signal(signal.SIGTERM, _request_stop)
    signal.signal(signal.SIGINT, _request_stop)
    logger.info("Worker started (engine=%s, queue=%s)", engine.model_version, queue_url)

    while not _stop:
        resp = sqs.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=20,  # long polling: no busy loop, fewer billed empty receives
            AttributeNames=["ApproximateReceiveCount"],
        )
        for message in resp.get("Messages", []):
            body = message["Body"]
            try:
                process_message(body, s3=s3, table=table, engine=engine)
            except Exception as exc:
                attempt = int(message["Attributes"]["ApproximateReceiveCount"])
                logger.exception("Processing failed (attempt %s/%s)", attempt, max_receives)
                if attempt >= max_receives:
                    try:
                        mark_failed(body, str(exc), table=table)
                    except Exception:
                        logger.exception("Could not mark the receipt as FAILED")
                continue  # not deleted: redelivered, then DLQ
            sqs.delete_message(QueueUrl=queue_url, ReceiptHandle=message["ReceiptHandle"])

    logger.info("Worker stopped")


if __name__ == "__main__":
    run()
