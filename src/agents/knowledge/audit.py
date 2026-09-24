# src/agents/knowledge/audit.py

from __future__ import annotations
import time
from datetime import datetime
from loguru import logger
from sqlalchemy import text

from src.infra.database import AsyncSessionLocal


class QueryAuditLog:
    """查询审计日志记录器。将每次知识检索链路持久化到 MySQL（knowledge_query_logs）。"""

    @staticmethod
    async def log(
        user_id: str,
        role: str,
        question: str,
        intent: str,
        channels: list[str],
        answer_preview: str,
        duration_ms: float,
        hallucination_check: dict | None = None,
    ) -> None:
        is_grounded = (
            hallucination_check.get("is_grounded") if hallucination_check else None
        )
        # 审计独立开启短会话并提交，与主查询事务解耦（主事务回滚不影响审计落库）
        async with AsyncSessionLocal() as session:
            await session.execute(
                text("""
                    INSERT INTO knowledge_query_logs
                        (user_id, role, question, intent, channels,
                         answer_preview, duration_ms, is_grounded, created_at)
                    VALUES
                        (:user_id, :role, :question, :intent, :channels,
                         :answer_preview, :duration_ms, :is_grounded, :created_at)
                """),
                {
                    "user_id": user_id,
                    "role": role,
                    "question": question[:1000],
                    "intent": intent,
                    "channels": ",".join(channels) if channels else "",
                    "answer_preview": answer_preview[:500],
                    "duration_ms": int(duration_ms),
                    "is_grounded": is_grounded,
                    "created_at": datetime.now(),
                },
            )
            await session.commit()
        logger.bind(audit=True).info(
            f"knowledge_query | user={user_id} | role={role} | intent={intent} | "
            f"channels={channels} | duration={duration_ms:.0f}ms | "
            f"grounded={is_grounded} | question={question[:80]}"
        )


class Timer:
    """简单计时器，用于测量检索耗时。"""

    def __init__(self):
        self._start = None

    def __enter__(self):
        self._start = time.perf_counter()
        return self

    def __exit__(self, *args):
        pass

    @property
    def elapsed_ms(self) -> float:
        if self._start is None:
            return 0.0
        return (time.perf_counter() - self._start) * 1000