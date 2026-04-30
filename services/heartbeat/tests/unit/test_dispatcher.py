from src.dispatcher import start_dispatcher


def test_no_jobs_when_empty():
    scheduler = start_dispatcher([])
    jobs = scheduler.get_jobs()
    assert len(jobs) == 0
    scheduler.shutdown(wait=False)


def test_valid_schedule_creates_job():
    dept = {
        "dept_id": "finance",
        "heartbeat": {
            "enabled": True,
            "schedule": "0 8 * * 1-5",
            "context_sources": [],
            "outbound_actions": [],
        },
    }
    scheduler = start_dispatcher([dept])
    jobs = scheduler.get_jobs()
    assert len(jobs) == 1
    assert jobs[0].id == "heartbeat_finance"
    scheduler.shutdown(wait=False)
