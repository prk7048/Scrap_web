from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.auth import current_user, current_user_or_extension_save_user
from app.core.config import get_settings
from app.db.models import ItemStatus, User
from app.db.session import get_db
from app.schemas.items import ItemDetailResponse, ItemListResponse, ItemResponse, SaveManyRequest, SaveUrlRequest
from app.services.items import get_item, get_item_artifact, list_items, resolve_artifact_path, retry_item, save_url

router = APIRouter(prefix="/api/items", tags=["items"])


@router.post("/save", response_model=ItemResponse)
def save_item(
    payload: SaveUrlRequest,
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(current_user_or_extension_save_user),
) -> ItemResponse:
    item, created = save_url(db, str(payload.url))
    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    return item


@router.post("/save-many", response_model=ItemListResponse)
def save_many_items(
    payload: SaveManyRequest,
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(current_user_or_extension_save_user),
) -> ItemListResponse:
    items = []
    created_any = False
    for url in payload.urls:
        item, created = save_url(db, str(url))
        items.append(item)
        created_any = created_any or created
    response.status_code = status.HTTP_201_CREATED if created_any else status.HTTP_200_OK
    return ItemListResponse(items=items)


@router.get("", response_model=ItemListResponse)
def get_items(
    q: str | None = None,
    topic: str | None = None,
    source: str | None = None,
    domain: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    status_filter: ItemStatus | None = Query(default=None, alias="status"),
    capture_status: ItemStatus | None = None,
    has_failure: bool | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> ItemListResponse:
    return ItemListResponse(
        items=list_items(
            db,
            query=q,
            topic=topic,
            source=source or domain,
            date_from=date_from,
            date_to=date_to,
            status=status_filter or capture_status,
            has_failure=has_failure,
        )
    )


@router.get("/{item_id}", response_model=ItemDetailResponse)
def get_saved_item(
    item_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> ItemDetailResponse:
    item = get_item(db, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    return item


@router.get("/{item_id}/artifacts/{artifact_id}")
def get_saved_item_artifact(
    item_id: str,
    artifact_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> FileResponse:
    result = get_item_artifact(db, item_id, artifact_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found")

    _, artifact = result
    try:
        artifact_path = resolve_artifact_path(Path(get_settings().data_dir), artifact)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact file not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    headers = {
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "no-referrer",
    }
    if artifact.mime_type in {"text/html", "application/pdf"}:
        headers["Content-Security-Policy"] = "sandbox; default-src 'none'; img-src data: blob:; style-src 'unsafe-inline'"

    return FileResponse(artifact_path, media_type=artifact.mime_type, headers=headers)


@router.post("/{item_id}/retry", response_model=ItemResponse)
def retry_saved_item(
    item_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> ItemResponse:
    try:
        return retry_item(db, item_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
