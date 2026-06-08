import os
from celery import Celery

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery = Celery("promptlens", broker=REDIS_URL, backend=REDIS_URL)
celery.conf.update(task_serializer="json", result_serializer="json", accept_content=["json"])


@celery.task(name="score_turn", bind=True, max_retries=3)
def score_turn(self, turn_id: int) -> dict:
    try:
        from ..db.client import SessionLocal
        from ..db.models import Turn
        from ..evaluators import EvaluatorChain

        db = SessionLocal()
        try:
            turn = db.query(Turn).filter(Turn.id == turn_id).first()
            if not turn:
                return {"skipped": True, "reason": "turn not found"}

            chain = EvaluatorChain()
            score, flags = chain.score("", turn.prompt_chars)
            turn.quality_score = score
            turn.flags = flags
            db.commit()
            return {"turn_id": turn_id, "score": score, "flags": flags}
        finally:
            db.close()
    except Exception as exc:
        raise self.retry(exc=exc, countdown=30)
