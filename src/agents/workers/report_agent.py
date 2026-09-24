from langchain.agents import create_agent
from langchain_core.tools import tool
from src.core.config import get_llm

"""
报告解读 Agent
"""


def create_report_agent():
    REPORT_SYSTEM_PROMPT = """你是天宫医疗的报告解读助手。
    你的职责：
    1. 解读患者上传的检验报告、影像报告
    2. 提取关键异常指标，用通俗语言解释含义
    3. 标注需要重点关注的项目
    4. 给出初步建议（是否需要复查、就诊等）

    回复格式：
    - 报告类型：xxx
    - 关键发现：xxx
    - 异常指标：xxx（正常范围：xxx，当前值：xxx）
    - 建议：xxx

    注意：解读结果仅供参考，最终诊断以医生为准。"""
    llm = get_llm()
    tools = []

    agent = create_agent(model=llm, system_prompt=REPORT_SYSTEM_PROMPT,tools= tools,name="report_agent")
    return agent

#全局单例
_report_agent = None

def get_report_agent():
    global _report_agent
    if _report_agent is None:
        _report_agent = create_report_agent()
    return _report_agent

