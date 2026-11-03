from fastapi import APIRouter

from app.database.database_operations import get_all_events


router = APIRouter(
    prefix="/api/events",
    tags=["History"]
)


@router.get("")
def retrieve_event_history():
    """Retrieve all previously created events."""

    events = get_all_events()

    return {
        "total_events": len(events),
        "events": events
    }