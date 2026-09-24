"""问诊纯逻辑单元测试：置信度加权、收敛判断、待追问症状筛选。

这一层不碰任何外部服务（无 LLM / Neo4j / Milvus / DB），只验证诊断推理的
纯函数逻辑，故确定性且零成本。图编排与多轮流转见 test_inquiry_flow.py。
"""
from __future__ import annotations

from src.agents.inquiry.state import CandidateDisease, PatientContext
from src.agents.inquiry.confidence import apply_context_weights, check_convergence
from src.agents.inquiry.neo4j_queries import get_pending_symptoms


def _disease(name, base, all_symptoms, matched=None):
    return CandidateDisease(
        name=name,
        base_confidence=base,
        confidence=base,
        matched_symptoms=matched or [],
        all_symptoms=all_symptoms,
    )


# ════════════════ apply_context_weights ════════════════

def test_weight_medical_history_bonus():
    """既往病史命中疾病名 → +0.15。"""
    cands = [_disease("胃炎", 0.50, ["腹痛", "恶心"])]
    ctx = PatientContext(medical_history=["慢性胃炎"])  # 包含"胃炎"子串
    out = apply_context_weights(cands, ctx, denied_symptoms=[])
    assert out[0].confidence == 0.65


def test_weight_long_term_memory_bonus():
    """长期记忆命中疾病名 → +0.10。"""
    cands = [_disease("肠炎", 0.40, ["腹泻"])]
    ctx = PatientContext(long_term_memories=["既往有肠炎发作记录"])
    out = apply_context_weights(cands, ctx, denied_symptoms=[])
    assert out[0].confidence == 0.50


def test_weight_denied_core_symptom_penalty():
    """否认某疾病的核心（独有）症状 → -0.20；共有症状被否认不扣分。"""
    # 反酸只属于胃炎（核心症状）；腹痛两病共有（非核心）
    gastritis = _disease("胃炎", 0.60, ["腹痛", "反酸"])
    enteritis = _disease("肠炎", 0.55, ["腹痛", "腹泻"])
    out = apply_context_weights([gastritis, enteritis], PatientContext(),
                                denied_symptoms=["反酸"])
    result = {c.name: c.confidence for c in out}
    assert result["胃炎"] == 0.40   # 0.60 - 0.20，核心症状被否认
    assert result["肠炎"] == 0.55   # 未受影响


def test_weight_shared_symptom_denied_no_penalty():
    """被否认的症状同时属于多个候选（非核心）→ 不扣分。"""
    gastritis = _disease("胃炎", 0.60, ["腹痛", "反酸"])
    enteritis = _disease("肠炎", 0.55, ["腹痛", "腹泻"])
    out = apply_context_weights([gastritis, enteritis], PatientContext(),
                                denied_symptoms=["腹痛"])  # 腹痛两病共有
    result = {c.name: c.confidence for c in out}
    assert result["胃炎"] == 0.60
    assert result["肠炎"] == 0.55


def test_weight_clamp_and_sort():
    """加权后限幅在 [0,1] 且按最终置信度降序重排。"""
    a = _disease("A", 0.95, ["s1"])   # +0.15 病史 → 1.10 → 限幅 1.0
    b = _disease("B", 0.30, ["s2"])
    ctx = PatientContext(medical_history=["患有A"])
    out = apply_context_weights([b, a], ctx, denied_symptoms=[])
    assert out[0].name == "A" and out[0].confidence == 1.0  # 限幅并排到最前
    assert out[1].name == "B"


# ════════════════ check_convergence ════════════════

def test_convergence_force_at_max_rounds():
    """达到轮次上限 → 强制结束 (True, True)，即便无候选。"""
    assert check_convergence([], current_round=10) == (True, True)


def test_convergence_no_candidates_continue():
    """未到上限且无候选 → 不结束 (False, False)。"""
    assert check_convergence([], current_round=2) == (False, False)


def test_convergence_top1_above_threshold():
    """Top1 置信度 ≥ 0.70 → 结束但非强制 (True, False)。"""
    cands = [_disease("胃炎", 0.75, []), _disease("肠炎", 0.60, [])]
    assert check_convergence(cands, current_round=1) == (True, False)


def test_convergence_top1_leads_top2():
    """Top1 与 Top2 差值 ≥ 0.30 → 结束 (True, False)。"""
    cands = [_disease("胃炎", 0.55, []), _disease("肠炎", 0.20, [])]
    assert check_convergence(cands, current_round=1) == (True, False)


def test_convergence_not_yet():
    """置信度不足且差距不够 → 继续追问 (False, False)。"""
    cands = [_disease("胃炎", 0.50, []), _disease("肠炎", 0.45, [])]
    assert check_convergence(cands, current_round=1) == (False, False)


# ════════════════ get_pending_symptoms ════════════════

async def test_pending_filters_known_and_sorts_by_discrimination():
    """待追问症状：剔除已确认/否认/问过的，按出现次数升序（区分度高的在前）。"""
    cands = [
        _disease("胃炎", 0.5, ["腹痛", "恶心", "反酸"]),
        _disease("肠炎", 0.5, ["腹痛", "腹泻"]),
        _disease("感冒", 0.5, ["腹痛", "发热"]),
    ]
    pending = await get_pending_symptoms(
        candidates=cands,
        confirmed_symptoms=["腹痛"],   # 已确认，排除
        denied_symptoms=["发热"],      # 已否认，排除
        asked_symptoms=["恶心"],       # 已问过，排除
    )
    names = [s for s, _ in pending]
    # 腹痛/发热/恶心 被排除，剩 反酸(1) 腹泻(1)，均出现 1 次
    assert set(names) == {"反酸", "腹泻"}
    assert all(cnt == 1 for _, cnt in pending)


async def test_pending_orders_low_count_first():
    """出现次数少（区分度高）的症状排在前面。"""
    cands = [
        _disease("胃炎", 0.5, ["共有症状", "独有A"]),
        _disease("肠炎", 0.5, ["共有症状", "独有B"]),
    ]
    pending = await get_pending_symptoms(cands, [], [], [])
    counts = dict(pending)
    assert counts["独有A"] == 1 and counts["独有B"] == 1
    assert counts["共有症状"] == 2
    # 独有症状（count=1）必须排在共有症状（count=2）之前
    assert pending[-1][0] == "共有症状"
