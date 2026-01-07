from fastapi import FastAPI, status, HTTPException, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel


app = FastAPI(debug=True)

templates = Jinja2Templates(directory='templates')
app.mount('/static', StaticFiles(directory='static'), name='static')

class MessageCreate(BaseModel):
    content: str

class Message(BaseModel):
    id: int
    content: str

messages_db: list[Message] = [Message(id=0, content="First post in FastAPI")]


@app.get('/web/messages', response_class=HTMLResponse)
async def get_messages_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse('index.html', context={'request': request, 'messages': messages_db})

@app.get('/web/messages/create', response_class=HTMLResponse)
async def get_create_message_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse('create.html', {'request': request})

@app.post('/web/messages', response_class=HTMLResponse)
async def create_message_form(request: Request, content: str = Form(...)) -> HTMLResponse:
    ind = max((msg.id for msg in messages_db), default=-1) + 1
    message = Message(id=ind, content=content)
    messages_db.append(message)
    return templates.TemplateResponse('index.html', {'request': request, 'messages': message})

@app.get('/web/messages/{message_id}', response_class=HTMLResponse)
async def get_message_detail_page(request: Request, message_id: int) -> HTMLResponse:
    for message in messages_db:
        if message.id == message_id:
            return templates.TemplateResponse('detail.html', {'request': request, 'message': message})
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")



@app.get('/messages', response_model=list[Message])
async def read_messages() -> list[Message]:
    return messages_db

@app.get('/messages/{message_id}', response_model=Message)
async def read_message(message_id: int) -> Message:
    for m in messages_db:
        if m.id == message_id:
            return m
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")


@app.post('/messages', response_model=Message, status_code=status.HTTP_201_CREATED)
async def create_message(message: MessageCreate) -> Message:
    ind = max((msg.id for msg in messages_db), default=-1) + 1
    m = Message(id=ind, content=message.content)
    messages_db.append(m)
    return m

@app.put("/messages/{message_id}", response_model=Message)
async def update_message(message_id: int, message_create: MessageCreate) -> Message:
    for i, message in enumerate(messages_db):
        if message.id == message_id:
            updated_message = Message(id=message_id, content=message_create.content)
            messages_db[i] = updated_message
            return updated_message
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")


@app.delete('/messages/{message_id}')
async def delete_message(message_id: int) -> dict:
    for i, m in enumerate(messages_db):
        if m.id == message_id:
            messages_db.pop(i)
            return {"detail": f"Message ID={message_id} deleted!"}
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message with this ID does not exist")

@app.delete('/messages')
async def delete_messages() -> dict:
    messages_db.clear()
    return {"detail": "DB cleared"}
