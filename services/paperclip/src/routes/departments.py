"""Department and agent registry endpoints."""
from fastapi import APIRouter, HTTPException

from src.db.connection import get_pool
from src.models import AgentRegister, AgentResponse, DepartmentCreate, DepartmentResponse
from src.services.department_service import DepartmentService

router = APIRouter(prefix="/departments", tags=["departments"])


@router.post("", response_model=DepartmentResponse, status_code=201)
async def create_department(body: DepartmentCreate):
    pool = await get_pool()
    svc = DepartmentService(pool)
    try:
        return await svc.create_department(
            name=body.name, display_name=body.display_name,
            slack_channel=body.slack_channel, hod_email=body.hod_email,
            data_zone=body.data_zone, escalation_rules=body.escalation_rules,
            config=body.config,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("", response_model=list[DepartmentResponse])
async def list_departments():
    pool = await get_pool()
    svc = DepartmentService(pool)
    return await svc.list_departments()


@router.post("/{dept}/agents", status_code=201)
async def register_agent(dept: str, body: AgentRegister):
    pool = await get_pool()
    svc = DepartmentService(pool)
    try:
        return await svc.register_agent(
            department=dept, agent_name=body.agent_name,
            agent_role=body.agent_role, worker_type=body.worker_type,
            endpoint_url=body.endpoint_url, skills=body.skills,
            data_scope=body.data_scope, permissions=body.permissions,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/{dept}/agents", response_model=list[AgentResponse])
async def list_agents(dept: str):
    pool = await get_pool()
    svc = DepartmentService(pool)
    return await svc.list_agents(dept)


@router.delete("/{dept}/agents/{name}")
async def deregister_agent(dept: str, name: str):
    pool = await get_pool()
    svc = DepartmentService(pool)
    removed = await svc.deregister_agent(dept, name)
    if not removed:
        raise HTTPException(status_code=404, detail=f"Agent '{name}' not found in '{dept}'")
    return {"status": "deregistered", "agent": name}
