"""智慧问诊全流程集成测试。

用假 LLM / Neo4j / Embedding / Milvus（见 inquiry_fakes.py）驱动真实的
LangGraph 编排，DB 用 conftest 的真实 waku_test 会话。覆盖四条主路径：
急症短路、模糊澄清、单轮直接收敛并落库、多轮追问后收敛。
"""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select

# 导入医疗模型，保证 Base.metadata 注册 patients / consultations / departments 三张表
import src.modules.medical.model  # noqa: F401
from src.modules.medical.model import Patient, Department, Consultation

from src.agents.inquiry.graph import InquiryDeps, run_inquiry
from src.agents.inquiry.state import InquiryPhase
from tests.modules.agents.inquiry_fakes import (
    FakeChatModel, FakeNeo4jDriver, FakeEmbeddingModel, FakeMilvusClient,
)


def _make_deps(db_session) -> InquiryDeps:
    """组装全假外部依赖 + 真实 DB 会话的依赖容器。"""
    return InquiryDeps(
        llm=FakeChatModel(),
        neo4j_driver=FakeNeo4jDriver(),
        embedding_model=FakeEmbeddingModel(),
        milvus_client=FakeMilvusClient(),
        db_session=db_session,
    )


@pytest_asyncio.fixture(loop_scope="session")
async def seed_patient(db_session):
    """插入一个科室 + 一名患者，供加载上下文 / 落库两个 DB 节点使用。"""
    dept = Department(name="消化内科", description="消化系统疾病")
    db_session.add(dept)
    patient = Patient(name="张三", gender="男", age=30,
                      medical_history="高血压", allergy_history="青霉素")
    db_session.add(patient)
    # flush 让后续同一会话内的查询能看到（尚未提交，随外层事务回滚）
    await db_session.flush()
    return patient


async def test_emergency_short_circuit(db_session):
    """首轮描述含急症信号 → 直接结束并给出急诊指引，不进入诊断流程。"""
    deps = _make_deps(db_session)
    reply, state = await run_inquiry(
        user_message="我突然胸口剧痛，还喘不上气",
        thread_id=f"t-{uuid.uuid4().hex[:8]}",
        deps=deps,
    )
    assert state.phase == InquiryPhase.END
    assert "120" in reply or "急诊" in reply
    # 急症短路发生在图查询之前，不应产出候选疾病
    assert state.candidate_diseases == []


async def test_vague_input_triggers_clarify(db_session):
    """首轮描述模糊、抽不出症状 → 进入澄清并等待用户补充。"""
    deps = _make_deps(db_session)
    reply, state = await run_inquiry(
        user_message="我最近感觉不太舒服",
        thread_id=f"t-{uuid.uuid4().hex[:8]}",
        deps=deps,
    )
    assert state.phase == InquiryPhase.CLARIFY
    assert state.round == 1          # 澄清节点推进一轮，等待下一次输入
    assert state.confirmed_symptoms == []
    assert reply                     # 有澄清追问话术


async def test_full_diagnosis_single_round_and_persist(db_session, seed_patient):
    """症状明确且高置信直接收敛：产出结论 + handoff，并把问诊记录写库。"""
    thread_id = f"t-{uuid.uuid4().hex[:8]}"
    deps = _make_deps(db_session)

    reply, state = await run_inquiry(
        user_message="我肚子疼，还恶心反酸",
        thread_id=thread_id,
        deps=deps,
        user_id=str(seed_patient.id),
    )

    # 流程走到 conclude → save_record → END
    assert state.phase == InquiryPhase.END
    assert reply
    # 命中症状：腹痛 / 恶心 / 反酸 三项，胃炎 3/4=0.75 触发收敛
    assert set(state.confirmed_symptoms) == {"腹痛", "恶心", "反酸"}

    payload = state.handoff_payload
    assert payload is not None
    assert payload.primary_disease == "胃炎"
    assert payload.primary_confidence >= 0.70
    assert payload.department == "消化内科"
    assert "胃镜" in payload.recommended_checks

    # 问诊记录已落库，且关联到正确的患者与科室
    row = (await db_session.execute(
        select(Consultation).where(Consultation.session_id == thread_id)
    )).scalar_one()
    assert row.diagnosis == "胃炎"
    assert row.patient_id == seed_patient.id
    dept = (await db_session.execute(
        select(Department).where(Department.name == "消化内科")
    )).scalar_one()
    assert row.department_id == dept.id


async def test_multi_round_ask_then_conclude(db_session, seed_patient):
    """症状不足以收敛 → 追问 → 用户补充 → 再查图谱后收敛。"""
    thread_id = f"t-{uuid.uuid4().hex[:8]}"
    deps = _make_deps(db_session)

    # 第一轮：只说"肚子疼"，候选置信度不足，进入追问、等待回答
    reply1, state1 = await run_inquiry(
        user_message="最近总是肚子疼",
        thread_id=thread_id,
        deps=deps,
        user_id=str(seed_patient.id),
    )
    assert state1.phase == InquiryPhase.SYMPTOM_CONFIRM
    assert state1.confirmed_symptoms == ["腹痛"]
    assert state1.pending_ask_symptoms          # 记录了本轮追问的症状
    assert reply1

    # 第二轮：补充"恶心、反酸"，解析后重查图谱，胃炎升到 0.75 收敛
    reply2, state2 = await run_inquiry(
        user_message="有恶心，还反酸",
        thread_id=thread_id,
        deps=deps,
        existing_state=state1,
    )
    assert state2.phase == InquiryPhase.END
    assert set(state2.confirmed_symptoms) == {"腹痛", "恶心", "反酸"}
    assert state2.pending_ask_symptoms == []    # 追问已被解析清空
    assert state2.handoff_payload.primary_disease == "胃炎"
    assert reply2
