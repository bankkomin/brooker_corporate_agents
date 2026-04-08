"""Heartbeat registration and monitoring endpoints."""
from fastapi import APIRouter, HTTPException

from src.db.connection import get_pool
from src.models import HeartbeatRequest, HeartbeatResponse
from src.services.department_service import DepartmentService
from src.services.heartbeat_service import HeartbeatService

router = APIRouter(tags=["heartbeat"])


@router.post("/heartbeat", response_model=HeartbeatResponse)
async def register_heartbeat(body: HeartbeatRequest):
    pool = await get_pool()

    dept_svc = DepartmentService(pool)
    try:
        await dept_svc.register_agent(
            department=body.department,
            agent_name=body.agent_name,
            agent_role=body.agent_role,
            endpoint_url=body.endpoint_url,
            skills=body.skills,
            data_scope=body.data_scope,
            permissions=body.permissions,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    hb_svc = HeartbeatService(pool)
    try:
        result = await hb_svc.update_heartbeat(body.agent_name, body.department)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/heartbeats")
async def list_heartbeats():
    pool = await get_pool()
    svc = HeartbeatService(pool)
    return await svc.list_heartbeats()
