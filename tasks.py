import os
from datetime import datetime

from celery import Celery
from pymongo import MongoClient
from bson import ObjectId

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")

celery_app = Celery("prescription_tasks", broker=REDIS_URL, backend=REDIS_URL)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    result_expires=3600,
    worker_prefetch_multiplier=1,
)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=5)
def process_prescription(self, image_path: str, username: str, doc_id: str):
    """
    Runs OCR in the background and updates MongoDB document.
    """
    from ocr_utils import analyze_prescription  # delayed import

    client = MongoClient(MONGO_URI)
    db = client["med_app"]
    prescriptions_col = db["prescriptions"]

    try:
        # Mark as processing
        prescriptions_col.update_one(
            {"_id": ObjectId(doc_id)},
            {
                "$set": {
                    "status": "processing",
                    "error_msg": "",
                    "processing_started_at": datetime.utcnow(),
                }
            },
        )

        self.update_state(state="PROGRESS", meta={"step": "Running OCR..."})

        analysis = analyze_prescription(image_path)

        result = analysis.get("prescription", {})
        quality = analysis.get("quality", {})
        interactions = analysis.get("interactions", [])

        prescriptions_col.update_one(
            {"_id": ObjectId(doc_id)},
            {
                "$set": {
                    "patient_name": result.get("name", ""),
                    "diagnosis": result.get("diagnosis", ""),
                    "medicines": result.get("medicines", []),
                    "quality": quality,
                    "interactions": interactions,
                    "status": "done",
                    "processed_at": datetime.utcnow(),
                    "error_msg": "",
                }
            },
        )

        return {"status": "done", "doc_id": doc_id}

    except Exception as exc:
        prescriptions_col.update_one(
            {"_id": ObjectId(doc_id)},
            {
                "$set": {
                    "status": "error",
                    "error_msg": str(exc),
                    "processed_at": datetime.utcnow(),
                }
            },
        )
        raise self.retry(exc=exc)

    finally:
        client.close()