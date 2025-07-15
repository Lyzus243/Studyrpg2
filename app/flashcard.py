# app/flashcard.py
from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from typing import List
from app.models import FlashcardDeck, Flashcard, User
from app.schemas import FlashcardDeckCreate, FlashcardCreate, FlashcardDeckRead, FlashcardRead
from app.auth import get_current_user
from app.crud import get_flashcards, create_flashcard_deck, create_user_flashcard
from app.database import get_async_session

flashcards_router = APIRouter(prefix="/flashcards", tags=["flashcards"])
templates = Jinja2Templates(directory="templates")

@flashcards_router.get("/page", response_class=HTMLResponse)
async def get_flashcards_page(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    flashcard_decks = await get_flashcards(db, current_user.id)
    return templates.TemplateResponse("flashcards.html", {
        "request": request,
        "current_user": current_user,
        "flashcard_sets": [FlashcardDeckRead.from_orm(fs) for fs in flashcard_decks]
    })

@flashcards_router.get("/", response_model=List[FlashcardDeckRead])
async def get_flashcard_decks(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    flashcard_decks = await get_flashcards(db, current_user.id)
    return [FlashcardDeckRead.from_orm(fd) for fd in flashcard_decks]

@flashcards_router.get("/{deck_id}", response_model=FlashcardDeckRead)
async def get_flashcard_deck(
    deck_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    result = await db.exec(select(FlashcardDeck).where(FlashcardDeck.id == deck_id))
    deck = result.first()
    if not deck or deck.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Deck not found or not authorized")
    return FlashcardDeckRead.from_orm(deck)

@flashcards_router.get("/{deck_id}/cards", response_model=List[FlashcardRead])
async def get_flashcards_api(
    deck_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    flashcards = await get_flashcards(db, deck_id)
    return [FlashcardRead.from_orm(f) for f in flashcards]

@flashcards_router.post("/", response_model=FlashcardRead)
async def create_flashcard_api(
    flashcard: FlashcardCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    flashcard_db = await create_user_flashcard(db, flashcard, current_user.id)
    return FlashcardRead.from_orm(flashcard_db)

@flashcards_router.post("/sets", response_model=FlashcardDeckRead)
async def create_flashcard_set_api(
    deck: FlashcardDeckCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    flashcard_deck = await create_flashcard_deck(db, deck.dict())
    return FlashcardDeckRead.from_orm(flashcard_deck)

@flashcards_router.post("/generate", response_model=FlashcardDeckRead)
async def generate_flashcards(
    data: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    deck_data = FlashcardDeckCreate(name=data["name"], topic=data["topic"], user_id=current_user.id)
    deck = FlashcardDeck(**deck_data.dict())
    db.add(deck)
    await db.commit()
    await db.refresh(deck)
    cards = [
        FlashcardCreate(deck_id=deck.id, question=card["question"], answer=card["answer"])
        for card in data.get("cards", [])
    ]
    for card in cards:
        flashcard = await create_user_flashcard(db, card, current_user.id)
    await db.commit()
    await db.refresh(deck)
    return FlashcardDeckRead.from_orm(deck)