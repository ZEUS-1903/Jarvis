"""Memory management for the UI: view, add, approve, delete.

These endpoints are driven by the *user* clicking in the UI, so unlike the
model's `remember` tool, anything added here is trusted and saved directly.
"""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.memory.policy import looks_secret
from app.memory.store import Category, Memory, MemoryNotFound

router = APIRouter(prefix="/memories")


class MemoriesResponse(BaseModel):
    active: list[Memory]
    pending: list[Memory]


class NewMemory(BaseModel):
    content: str = Field(min_length=1, max_length=300)
    category: Category = "other"


@router.get("", response_model=MemoriesResponse)
async def list_memories(request: Request) -> MemoriesResponse:
    store = request.app.state.memories
    return MemoriesResponse(active=await store.list("active"), pending=await store.list("pending"))


@router.post("", response_model=Memory, status_code=201)
async def add_memory(body: NewMemory, request: Request) -> Memory:
    if looks_secret(body.content):
        raise HTTPException(422, "That looks like a secret (password, card number...). Not saved.")
    return await request.app.state.memories.add(body.content, body.category, "active", "user")


@router.post("/{memory_id}/approve", response_model=Memory)
async def approve_memory(memory_id: int, request: Request) -> Memory:
    try:
        return await request.app.state.memories.approve(memory_id)
    except MemoryNotFound:
        raise HTTPException(404, "memory not found")


@router.delete("/{memory_id}", status_code=204)
async def delete_memory(memory_id: int, request: Request) -> None:
    try:
        await request.app.state.memories.delete(memory_id)
    except MemoryNotFound:
        raise HTTPException(404, "memory not found")
