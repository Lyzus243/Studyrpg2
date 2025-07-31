from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import SQLAlchemyError
from typing import List
from app import models, schemas, crud
from app.database import get_async_session
from app.auth_deps import get_current_user
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

shop_router = APIRouter(prefix="", tags=["shop"])

@shop_router.get("/items", response_model=List[schemas.ItemRead])
async def get_shop_items(
    db: AsyncSession = Depends(get_async_session),
    current_user: models.User = Depends(get_current_user)
):
    try:
        if not current_user:
            logger.warning("Unauthorized attempt to list shop items")
            raise HTTPException(status_code=401, detail="Authentication required")
        result = await db.execute(select(models.Item).order_by(models.Item.id))
        items = result.scalars().all()
        return [schemas.ItemRead.model_validate(item) for item in items]
    except SQLAlchemyError as e:
        logger.error(f"Database error fetching shop items for user {current_user.id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch shop items: Database error")
    except Exception as e:
        logger.error(f"Unexpected error fetching shop items for user {current_user.id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch shop items: {str(e)}")

@shop_router.post("/purchase", response_model=schemas.UserItemRead)
async def purchase_item(
    purchase: schemas.PurchaseCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user: models.User = Depends(get_current_user)
):
    try:
        if not current_user:
            logger.warning("Unauthorized attempt to purchase item")
            raise HTTPException(status_code=401, detail="Authentication required")
        
        # FIX: Get fresh user object from session
        result = await db.execute(
            select(models.User)
            .where(models.User.id == current_user.id)
            .options(selectinload(models.User.items))
        )
        user = result.scalars().first()
        
        # FIX: Get item with locking to prevent race conditions
        result = await db.execute(
            select(models.Item)
            .where(models.Item.id == purchase.item_id)
            .with_for_update()
        )
        item = result.scalars().first()
        
        if not item:
            logger.warning(f"Item {purchase.item_id} not found for purchase by user {user.id}")
            raise HTTPException(status_code=404, detail="Item not found")
            
        if user.currency < item.price:
            logger.warning(f"Insufficient coins for user {user.id} to purchase item {item.id}")
            raise HTTPException(status_code=400, detail="Insufficient coins")
            
        user.currency -= item.price
        user_item = models.UserItem(
            user_id=user.id,
            item_id=item.id,
            purchased_at= datetime.utcnow()
        )
        
        # FIX: Add to session and commit
        db.add(user_item)
        await db.commit()
        await db.refresh(user_item)
        
        logger.info(f"User {user.id} purchased item {item.id}")
        return schemas.UserItemRead.model_validate(user_item)
        
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        logger.error(f"Database error in purchase for user {user.id}, item {purchase.item_id}: {str(e)}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Failed to purchase item: Database error")
    except Exception as e:
        logger.error(f"Unexpected error in purchase for user {user.id}, item {purchase.item_id}: {str(e)}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to purchase item: {str(e)}")

@shop_router.get("/inventory", response_model=List[schemas.UserItemRead])
async def get_user_inventory(
    db: AsyncSession = Depends(get_async_session),
    current_user: models.User = Depends(get_current_user)
):
    try:
        if not current_user:
            logger.warning("Unauthorized attempt to view inventory")
            raise HTTPException(status_code=401, detail="Authentication required")
            
        # FIX: Query UserItem directly instead of through User
        result = await db.execute(
            select(models.UserItem)
            .where(models.UserItem.user_id == current_user.id)
            .order_by(models.UserItem.purchased_at.desc())
        )
        user_items = result.scalars().all()
        
        return [schemas.UserItemRead.model_validate(item) for item in user_items]
    except SQLAlchemyError as e:
        logger.error(f"Database error fetching inventory for user {current_user.id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch inventory: Database error")
    except Exception as e:
        logger.error(f"Unexpected error fetching inventory for user {current_user.id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch inventory: {str(e)}")