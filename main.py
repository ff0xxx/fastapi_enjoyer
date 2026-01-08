from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


app = FastAPI(title="Messages CRUD")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class MessageCreate(BaseModel):
    content: str

class MessageUpdate(BaseModel):
    content: str | None = None

class Message(BaseModel):
    id: int
    content: str

messages_db: list[Message] = [Message(id=0, content='My first message')]


def next_id() -> int:
    return max((m.id for m in messages_db), default=-1) + 1

@app.get('/messages', response_model=list[Message])
async def get_messages() -> list[Message]:
    return messages_db

@app.post('/messages', response_model=Message, status_code=201)
async def create_message(payload: MessageCreate) -> Message:
    message = Message(id=next_id(), content=payload.content)
    messages_db.append(message)
    return message


def get_index(index) -> int:
    for i, m in enumerate(messages_db):
        if m.id == index:
            return i
    return -1

@app.get('/messages/{message_id}', response_model=Message)
async def get_message(message_id: int) -> Message:
    inx = get_index(message_id)
    if inx == -1:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    return messages_db[inx]

@app.patch('/messages/{message_id}', response_model=Message)
async def update_message(message_id: int, payload: MessageUpdate) -> Message:
    inx = get_index(message_id)
    if inx == -1:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    if payload.content is not None:
        messages_db[inx].content = payload.content
    return messages_db[inx]

@app.put('/messages/{message_id}', response_model=Message)
async def replace_message(message_id: int, payload: MessageCreate) -> Message:
    inx = get_index(message_id)
    if inx == -1:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    message = Message(id=message_id, content=payload.content)
    messages_db[inx] = message
    return message

@app.delete('/messages/{message_id}', status_code=204)
async def delete_message(message_id: int):
    inx = get_index(message_id)
    if inx == -1:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    messages_db.pop(inx)