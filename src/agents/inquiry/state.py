from __future__ import annotations
from enum import Enum
from typing import Annotated
from langchain_core.messages import BaseMessage
from langgraph.graph import add_messages
from pydantic import BaseModel, Field


#阶段枚举，驱动LangGraph路由逻辑
class InquiryPhase(str, Enum):
    CLARIFY = "CLARIFY"            #用户描述模糊，引导澄清

    GRAPH_QUERY = "GRAPH_QUERY"    #有明确症状，进行Neo4j图查询

    SYMPTOM_CONFIRM = "SYMPTOM_CONFIRM"  #追问候选症状

    COMPLICATION_CHECK = "COMPLICATION_CHECK" #追问并发症症状

    CONCLUDE = "CONCLUDE"          #输出诊断结果

    HANDOFF = "HANDOFF"            #咨询转接

    END = "END"                    #结束会话


#候选疾病实体类
class CandidateDisease(BaseModel):
    name: str
    confidence: float=0.0           #置信度,加权后
    base_confidence: float=0.0      #基础置信度,命中症状数/总症状数
    matched_symptoms: list[str] = Field(default_factory=list)  #已匹配上的症状
    all_symptoms: list[str] = Field(default_factory=list)    #该疾病的所有症状
    department: str = ""   #建议科室
    checks: list[str] = Field(default_factory=list)  #建议检查项
    complications: list[str] = Field(default_factory=list)  # 并发症


#患者上下文,从外部系统加载
class PatientContext(BaseModel):
    patient_id: int|None = None
    age: int | None = None
    gender: str | None = None  # "男" / "女"
    allergy_history: list[str] = Field(default_factory=list)  # 过敏史
    medical_history: list[str] = Field(default_factory=list)  # 既往病史
    long_term_memories: list[str] = Field(default_factory=list)  # Milvus 长期记忆摘要


# ── 移交数据包（传给 Inquiry Worker Agent） ──────────────────────────────
class InquiryHandoffPayload(BaseModel):
    patient_id: int | None = None             # 患者ID
    patient_context: dict = Field(default_factory=dict)            # 患者上下文
    confirmed_symptoms: list[str] = Field(default_factory=list)     # 已确认症状
    denied_symptoms: list[str] = Field(default_factory=list)        # 拒绝的症状
    unmatched_symptoms: list[str] = Field(default_factory=list)     # 未匹配上的症状
    primary_disease: str = ""                                       # 主诊断疾病
    primary_confidence: float = 0.0                                 # 主诊断的置信度
    suspected_diseases: list[str] = Field(default_factory=list)      # 疑似疾病
    department: str = ""                                            # 建议科室
    recommended_checks: list[str] = Field(default_factory=list)      # 建议检查
    total_rounds: int = 0                                            # 总轮数
    session_id: str = ""                                             # 会话ID

# ── 主状态对象：在 LangGraph 节点间流转的"黑板" ──────────────────────────
class InquiryState(BaseModel):
    # 对话消息历史（add_messages 注解让 LangGraph 自动追加而非覆盖）
    messages: Annotated[list[BaseMessage], add_messages] = Field(default_factory=list)

    # 流程控制
    phase: InquiryPhase = InquiryPhase.CLARIFY
    round: int = 0                    # 当前轮次（1~10）
    session_id: str = ""

    # 症状追踪
    confirmed_symptoms: list[str] = Field(default_factory=list) # 确认症状
    denied_symptoms: list[str] = Field(default_factory=list)  # 否认症状
    unmatched_symptoms: list[str] = Field(default_factory=list)  # 图谱外症状
    asked_symptoms: list[str] = Field(default_factory=list)      # 已问过，不重复

    # 诊断推理
    candidate_diseases: list[CandidateDisease] = Field(default_factory=list)

    # 患者上下文
    patient_context: PatientContext = Field(default_factory=PatientContext)

    # 结论
    handoff_payload: InquiryHandoffPayload | None = None
    force_conclude: bool = False      # True = 达到 10 轮强制结束

    # 节点间临时传递数据
    pending_ask_symptoms: list[str] = Field(default_factory=list)  # 本轮准备追问的症状
