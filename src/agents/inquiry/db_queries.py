from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.inquiry.state import PatientContext
from src.modules.medical.model import Patient, Consultation
from loguru import logger

async def load_patient_context(patient_id:int|None,
                               db:AsyncSession|None,
                               recent_consultations_limit:int=5) -> PatientContext :
    """
        从 PostgreSQL 加载患者上下文：基本信息 + 近期问诊记录。
        patient_id 为 None 时返回空上下文。
        db 为 None 时自动创建 session。
        """
    if patient_id is None:
        return PatientContext()
    from src.infra.database import AsyncSessionLocal
    _own_session = db is None
    if _own_session:
        db = AsyncSessionLocal()
    try:
        patient_result = await db.execute(
            select(Patient).where(Patient.id == patient_id)
        )
        patient = patient_result.scalar_one_or_none()
        if not patient:
            logger.warning(f"患者 ID {patient_id} 不存在")
            return PatientContext()
        #解析既往病史和过敏史，以逗号分割存储
        medical_history = [item.strip() for item in patient.medical_history.split(",")] if patient.medical_history else []
        allergy_history = [item.strip() for item in patient.allergy_history.split(",")] if patient.allergy_history else []

        #获取近期问诊记录
        consultations_result  = await db.execute(
            select(Consultation).where(Consultation.patient_id==patient_id).order_by(Consultation.created_at.desc()).limit(recent_consultations_limit)
        )
        consultations = consultations_result.scalars().all()
        for c in consultations:
            if c.diagnosis and c.diagnosis not in medical_history:
                medical_history.append(c.diagnosis)

        return PatientContext(
                    patient_id=patient_id,
                    age=patient.age,
                    gender=patient.gender,
                    allergy_history=allergy_history,
                    medical_history=medical_history
                )
    except Exception as e:
        logger.error(f"加载患者上下文失败: {e}")
        return PatientContext()
    finally:
        if _own_session:
            await db.close()

async def save_consultation_record(
        patient_id:int|None,
        session_id:str,
        chief_complaint:str,
        diagnosis:str|None,
        department_name:str|None,
        urgency_level:str|None,
        db:AsyncSession|None,
        )->int|None:
    """
    保存问诊记录
    """
    from src.infra.database import AsyncSessionLocal
    _own_session = db is None
    if _own_session:
        db = AsyncSessionLocal()
    try:
        from src.modules.medical.model import Department
        dept_result = await db.execute(
        select(Department).where(Department.name == department_name))
        dept = dept_result.scalar_one_or_none()
        dept_id = dept.id if dept else None
        consultation = Consultation(
            patient_id=patient_id,  # 未登录用户为 None，存 NULL
            department_id=dept_id,
            chief_complaint=chief_complaint,
            diagnosis=diagnosis,
            urgency_level=urgency_level,
            session_id=session_id,
        )
        db.add(consultation)
        await db.commit()
        await db.refresh(consultation)
        logger.info(f"问诊记录已保存，ID={consultation.id}")
        return consultation.id

    except Exception as e:
        await db.rollback()
        logger.error(f"保存问诊记录失败: {e}")
        return None
    finally:
        if _own_session:
            await db.close()