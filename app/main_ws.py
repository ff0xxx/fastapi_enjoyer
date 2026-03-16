from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi import FastAPI, WebSocket, Request
from starlette.websockets import WebSocketDisconnect


app = FastAPI()
templates = Jinja2Templates(directory='templates')


@app.get('/', response_class=HTMLResponse)
def read_index(request: Request):
    return templates.TemplateResponse('index.html', {'request': request})


class ConnectionManager:
    def __init__(self):
        self.connections: list[WebSocket] = []

    async def connect(self, websocket):
        await websocket.accept()
        self.connections.append(websocket)

    async def broadcast(self, data: str):
        for connection in self.connections:
            await connection.send_text(data)

manager = ConnectionManager()

@app.websocket('/ws/{client_id}')
async def websocket_endpoint(client_id: int, websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await manager.broadcast(f'Client {client_id}: {data}')
    except WebSocketDisconnect as e:
        manager.connections.remove(websocket)
        print(f'Connection closed {e.code}')