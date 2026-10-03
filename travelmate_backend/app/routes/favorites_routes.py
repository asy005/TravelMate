from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, Any

from app.database import get_db
from app.models.favorites import Favorite
from app.services.auth_utils import get_current_user

router = APIRouter(prefix="/favorites", tags=["favorites"])


class FavoriteCreate(BaseModel):
    destination_name: Optional[str] = None
    destination_payload: Optional[Any] = None


@router.get("/")
def get_favorites(user=Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(Favorite).filter(Favorite.user_id == user.id).all()


@router.post("/add")
def add_favorite(
    destination_id: int,
    payload: FavoriteCreate,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Already saved? Avoid duplicate rows for the same user/destination.
    existing = db.query(Favorite).filter(
        Favorite.user_id == user.id,
        Favorite.destination_id == destination_id,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Already saved in favorites")

    dest_payload = payload.destination_payload if isinstance(payload.destination_payload, dict) else {}

    new_fav = Favorite(
        user_id=user.id,
        destination_id=destination_id,
        name=payload.destination_name or dest_payload.get("name"),
        country=dest_payload.get("country"),
        image=dest_payload.get("image") or dest_payload.get("thumbnail_url"),
    )
    db.add(new_fav)
    db.commit()
    db.refresh(new_fav)
    return {"msg": "Added", "favorite_id": new_fav.id}


@router.delete("/{fav_id}")
def delete_favorite(fav_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    fav = db.query(Favorite).filter(
        Favorite.id == fav_id,
        Favorite.user_id == user.id,
    ).first()

    if not fav:
        raise HTTPException(status_code=404, detail="Not found")

    db.delete(fav)
    db.commit()
    return {"msg": "Deleted"}
