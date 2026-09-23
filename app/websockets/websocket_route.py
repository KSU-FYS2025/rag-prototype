import inspect

from fastapi.params import Query
from starlette.websockets import WebSocket
from typing import (
    Annotated,
    Any,
    Callable,
    Protocol,
    ParamSpec,
    Concatenate,
    Coroutine,
    runtime_checkable,
)

P = ParamSpec("P")


@runtime_checkable
class SupportsHandle(Protocol):
    async def handle(self) -> None: ...


@runtime_checkable
class SupportsHandleLoop(Protocol):
    async def handle_loop(self) -> None: ...


type WebSocketHandler = SupportsHandle | SupportsHandleLoop


def websocket_route(
    websocket_class: Callable[Concatenate[WebSocket, P], WebSocketHandler],
) -> Callable[Concatenate[WebSocket, P], Coroutine[Any, Any, None]]:
    async def route(websocket, *args: P.args, **kwargs: P.kwargs) -> None:
        handler: WebSocketHandler = websocket_class(websocket, *args, **kwargs)
        match handler:
            case SupportsHandle() as h:
                await h.handle()
            case SupportsHandleLoop() as h:
                await handler.handle_loop()

    return route
