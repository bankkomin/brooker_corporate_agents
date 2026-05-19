"""API endpoints for venture-monitor integration."""
import logging

from fastapi import APIRouter, HTTPException, Request

from .auth import AuthError, extract_claims
from .rate_limit import limiter

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/vm", tags=["venture-monitor"])


@router.get("/fund-scores")
@limiter.limit("20/minute")
async def get_fund_scores(request: Request):
    """Get latest fund risk scores from venture-monitor."""
    try:
        extract_claims(request)
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message) from e

    try:
        import os

        from services.shared.vm_bridge import VentureMonitorBridge
        bridge = VentureMonitorBridge(base_url=os.environ.get("VM_BASE_URL", "http://localhost:8000"))
        scores = await bridge.get_fund_scores()
        return {"scores": scores}
    except ImportError:
        raise HTTPException(501, "VM bridge not available") from None
    except Exception as e:
        raise HTTPException(502, f"Venture monitor unavailable: {e}") from e


@router.get("/fund-scores/{fund_id}")
@limiter.limit("20/minute")
async def get_fund_score(fund_id: int, request: Request):
    """Get score details for a specific fund."""
    try:
        extract_claims(request)
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message) from e

    try:
        import os

        from services.shared.vm_bridge import VentureMonitorBridge
        bridge = VentureMonitorBridge(base_url=os.environ.get("VM_BASE_URL", "http://localhost:8000"))
        return await bridge.get_fund_score(fund_id)
    except ImportError:
        raise HTTPException(501, "VM bridge not available") from None
    except Exception as e:
        raise HTTPException(502, f"Venture monitor unavailable: {e}") from e


@router.get("/alerts")
@limiter.limit("20/minute")
async def get_vm_alerts(request: Request, severity: str = "high"):
    """Get high-severity signals from venture-monitor."""
    try:
        extract_claims(request)
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message) from e

    try:
        import os

        from services.shared.vm_bridge import VentureMonitorBridge
        bridge = VentureMonitorBridge(base_url=os.environ.get("VM_BASE_URL", "http://localhost:8000"))
        signals = await bridge.get_high_severity_signals(min_severity=severity)
        return {"signals": signals}
    except ImportError:
        raise HTTPException(501, "VM bridge not available") from None
    except Exception as e:
        raise HTTPException(502, f"Venture monitor unavailable: {e}") from e


@router.get("/reconciliation-summary")
@limiter.limit("10/minute")
async def get_reconciliation_summary(request: Request):
    """Get latest reconciliation status from venture-monitor."""
    try:
        extract_claims(request)
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message) from e

    try:
        import os

        from services.shared.vm_bridge import VentureMonitorBridge
        bridge = VentureMonitorBridge(base_url=os.environ.get("VM_BASE_URL", "http://localhost:8000"))
        return {"reconciliations": await bridge.get_reconciliation_summary()}
    except ImportError:
        raise HTTPException(501, "VM bridge not available") from None
    except Exception as e:
        raise HTTPException(502, f"Venture monitor unavailable: {e}") from e
