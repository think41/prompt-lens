from celery import Celery

from ..core.config import settings

celery = Celery("promptlens", broker=settings.redis_url, backend=settings.redis_url)
celery.conf.update(task_serializer="json", result_serializer="json", accept_content=["json"])


@celery.task(name="score_turn", bind=True, max_retries=3)
def score_turn(self, turn_id: int) -> dict:
    try:
        from ..db.client import SessionLocal
        from ..db.models import Turn
        from ..evaluators.repetition import RepetitionDetector

        with SessionLocal() as db:
            from ..db.models import Session

            turn = db.query(Turn).filter(Turn.id == turn_id).first()
            if not turn:
                return {"skipped": True, "reason": "turn not found"}

            session = db.query(Session).filter_by(session_id=turn.session_id).first()

            # Start from hook pre-score — text evaluators ran there (no raw text in DB).
            # Only add DB-dependent signals here.
            base_score = float(turn.quality_score or 1.0)
            base_flags = list(turn.flags or [])

            rep_delta, rep_flags = RepetitionDetector().evaluate(
                turn.prompt_hash, turn.session_id, db
            )

            new_score = max(0.0, min(1.0, round(base_score + rep_delta, 2)))
            new_flags = base_flags + rep_flags

            turn.quality_score = new_score
            turn.flags = new_flags
            db.commit()

            from ..services.langfuse_service import send_turn_trace

            send_turn_trace(
                session_id=turn.session_id,
                turn_index=turn.turn_index,
                quality_score=new_score,
                flags=new_flags,
                prompt_chars=turn.prompt_chars,
                developer_id=turn.developer_id,
                team_id=turn.team_id,
                project_name=session.project_name if session else None,
            )

            return {"turn_id": turn_id, "score": new_score, "flags": new_flags}
    except Exception as exc:
        raise self.retry(exc=exc, countdown=30) from exc


@celery.task(name="score_session", bind=True, max_retries=3)
def score_session(self, session_id: str) -> dict:
    try:
        from ..db.client import SessionLocal
        from ..db.models import Session, ToolEvent, Turn
        from ..services.session_score import compute_session_score

        with SessionLocal() as db:
            turns = db.query(Turn).filter(Turn.session_id == session_id).all()
            tool_events = db.query(ToolEvent).filter(ToolEvent.session_id == session_id).all()

            score, flags = compute_session_score(turns, tool_events)

            session = db.query(Session).filter_by(session_id=session_id).first()
            if session:
                session.orchestration_score = score
                session.session_flags = flags
                db.commit()

        return {"session_id": session_id, "orchestration_score": score, "session_flags": flags}
    except Exception as exc:
        raise self.retry(exc=exc, countdown=30) from exc
