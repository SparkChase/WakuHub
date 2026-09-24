"""问诊全流程测试用的假外部依赖（LLM / Neo4j / Embedding / Milvus）。

设计原则：只替换「跨进程的外部服务」，图编排、路由、状态流转、症状标准化三层
管线、Neo4j 查询函数全部跑真实代码，故这是一次贴近真实的集成测试，且确定性、
零 API 费用、不依赖任何中间件在线。DB 部分用 conftest 的真实 db_session（waku_test）。
"""
from __future__ import annotations

import json
from contextlib import asynccontextmanager

from langchain_core.messages import AIMessage

from src.agents.inquiry.symptom_normalizer import SymptomsOutput

# ── 症状口语 → 标准术语映射（越具体的写在前面，命中即停）──────────────────
_SYMPTOM_KEYWORDS: list[tuple[str, str]] = [
    ("肚子疼", "腹痛"), ("肚子痛", "腹痛"), ("腹痛", "腹痛"),
    ("拉肚子", "腹泻"), ("腹泻", "腹泻"),
    ("恶心", "恶心"), ("想吐", "恶心"),
    ("反酸", "反酸"), ("烧心", "反酸"),
    ("发烧", "发热"), ("发热", "发热"),
    ("咳嗽", "咳嗽"),
    ("流鼻涕", "流涕"), ("流涕", "流涕"),
    ("嗓子疼", "咽痛"), ("咽痛", "咽痛"),
    ("头疼", "头痛"), ("头痛", "头痛"),
]

# ── 急症关键词（命中任一即判急症）────────────────────────────────────────
_EMERGENCY_KEYWORDS = [
    "胸痛", "胸口", "呼吸困难", "喘不上气", "昏迷", "意识不清",
    "大量出血", "剧烈头痛", "抽搐", "休克", "中风", "偏瘫", "失语",
]


def _extract_symptoms(text: str) -> list[str]:
    """从一段中文描述里按关键词抽取标准症状术语，去重保序。"""
    found: list[str] = []
    for kw, std in _SYMPTOM_KEYWORDS:
        if kw in text and std not in found:
            found.append(std)
    return found


def _user_input_after(content: str, marker: str = "用户描述：") -> str:
    """从格式化后的 prompt 中取回填进去的用户输入（marker 之后到行尾）。"""
    if marker not in content:
        return content
    return content.split(marker, 1)[1].split("\n", 1)[0]


class _StructuredExtractor:
    """模拟 llm.with_structured_output(SymptomsOutput) 的返回对象。"""

    async def ainvoke(self, messages):
        prompt = messages[0].content
        user_input = _user_input_after(prompt)
        return SymptomsOutput(symptoms=_extract_symptoms(user_input))


class FakeChatModel:
    """按 prompt 内容分派的确定性假 LLM。

    覆盖问诊流程用到的全部调用：症状抽取（结构化输出）、急症识别、澄清、
    追问话术、口语化、解析用户回答、生成结论。
    """

    def with_structured_output(self, schema):
        return _StructuredExtractor()

    async def ainvoke(self, messages):
        content = messages[0].content

        # 急症识别：扫描用户输入里的急症关键词
        if "判断以下用户描述是否包含急症关键词" in content:
            user_input = _user_input_after(content)
            hit = next((k for k in _EMERGENCY_KEYWORDS if k in user_input), None)
            payload = ({"is_emergency": True, "reason": f"出现急症信号：{hit}"}
                       if hit else {"is_emergency": False, "reason": ""})
            return AIMessage(content=json.dumps(payload, ensure_ascii=False))

        # 解析用户对追问的回答：把回答里提到的症状记为 confirmed
        if "判断每个症状的状态" in content:
            user_answer = _user_input_after(content, "患者的回答是：\n")
            confirmed = _extract_symptoms(user_answer)
            return AIMessage(content=json.dumps(
                {"confirmed": confirmed, "denied": [], "unknown": []},
                ensure_ascii=False,
            ))

        # 口语化：原样回显输入列表，保证长度一致
        if "转换为患者容易理解的口语表达" in content:
            raw = _user_input_after(content, "症状列表：")
            try:
                items = json.loads(raw)
            except Exception:
                items = []
            return AIMessage(content=json.dumps(items, ensure_ascii=False))

        # 澄清引导
        if "引导患者进一步描述" in content:
            return AIMessage(content="能再具体说说哪里不舒服吗？比如部位、持续多久了？")

        # 追问话术
        if "转化为自然、口语化的追问语句" in content:
            return AIMessage(content="请问您有没有恶心、反酸这些情况呢？有的话告诉我。")

        # 生成诊断结论
        if "生成一段清晰、友好的诊断结论" in content:
            return AIMessage(content="根据您的症状，最可能是胃炎，建议到消化内科就诊。是否现在预约挂号？")

        return AIMessage(content="（未预期的 prompt，返回占位）")


# ════════════════ 假 Neo4j：一张最小疾病图谱 ════════════════
_DISEASE_GRAPH: dict[str, dict] = {
    "胃炎": {
        "symptoms": ["腹痛", "恶心", "反酸", "腹胀"],
        "department": "消化内科",
        "checks": ["胃镜", "碳13呼气试验"],
        "complications": ["胃溃疡"],
    },
    "肠炎": {
        "symptoms": ["腹痛", "腹泻", "发热"],
        "department": "消化内科",
        "checks": ["便常规"],
        "complications": [],
    },
    "感冒": {
        "symptoms": ["发热", "咳嗽", "流涕", "咽痛"],
        "department": "呼吸内科",
        "checks": ["血常规"],
        "complications": [],
    },
}
_SYMPTOM_UNIVERSE = {s for info in _DISEASE_GRAPH.values() for s in info["symptoms"]}


class _FakeResult:
    def __init__(self, rows: list[dict]):
        self._rows = rows

    async def data(self):
        return self._rows


class _FakeSession:
    async def run(self, cypher: str, **params):
        # 候选疾病查询（按命中症状数 / 总症状数 排序）
        if "confirmed_symptoms" in params:
            confirmed = set(params["confirmed_symptoms"])
            rows = []
            for name, info in _DISEASE_GRAPH.items():
                matched = [s for s in info["symptoms"] if s in confirmed]
                if not matched:
                    continue
                total = len(info["symptoms"])
                rows.append({
                    "disease": name,
                    "matched_symptoms": matched,
                    "matched_count": len(matched),
                    "total_symptoms": total,
                    "base_confidence": len(matched) / total,
                })
            rows.sort(key=lambda r: r["base_confidence"], reverse=True)
            return _FakeResult(rows[: params.get("top_k", 10)])

        # 症状精确匹配（标准化第二层）
        if "RETURN s.name AS name" in cypher:
            names = params.get("names", [])
            return _FakeResult([{"name": n} for n in names if n in _SYMPTOM_UNIVERSE])

        names = params.get("names", [])

        # enrich：全部症状
        if "collect(s.name) AS symptoms" in cypher:
            return _FakeResult([{"disease": d, "symptoms": _DISEASE_GRAPH[d]["symptoms"]}
                                for d in names if d in _DISEASE_GRAPH])
        # enrich：科室
        if "dept.name AS department" in cypher:
            return _FakeResult([{"disease": d, "department": _DISEASE_GRAPH[d]["department"]}
                                for d in names if d in _DISEASE_GRAPH])
        # enrich：检查项
        if "collect(c.name) AS checks" in cypher:
            return _FakeResult([{"disease": d, "checks": _DISEASE_GRAPH[d]["checks"]}
                                for d in names if d in _DISEASE_GRAPH])
        # enrich：并发症
        if "collect(comp.name) AS complications" in cypher:
            return _FakeResult([{"disease": d, "complications": _DISEASE_GRAPH[d]["complications"]}
                                for d in names if d in _DISEASE_GRAPH])

        return _FakeResult([])


class FakeNeo4jDriver:
    @asynccontextmanager
    async def session(self):
        yield _FakeSession()


class FakeEmbeddingModel:
    """未匹配症状为空时不会被调用；提供以防语义兜底路径被触发。"""

    async def aembed_documents(self, texts):
        return [[0.0] * 8 for _ in texts]


class FakeMilvusClient:
    def search(self, *args, **kwargs):
        return []
