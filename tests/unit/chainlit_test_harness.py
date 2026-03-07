from __future__ import annotations

import importlib
import sys
from dataclasses import dataclass, field
from types import ModuleType
from typing import Any


class FakeUserSession:
    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value


@dataclass(frozen=True)
class FakeAction:
    name: str
    payload: dict[str, Any]
    label: str
    tooltip: str


@dataclass(frozen=True)
class FakeChatProfile:
    name: str
    display_name: str
    markdown_description: str
    default: bool
    starters: list[Any]


@dataclass(frozen=True)
class FakeStarter:
    label: str
    message: str
    icon: str


@dataclass(frozen=True)
class FakeUser:
    identifier: str
    display_name: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class FakeMessage:
    content: str = ""
    actions: list[Any] = field(default_factory=list)
    sent: bool = False

    async def send(self) -> FakeMessage:
        self.sent = True
        return self

    async def stream_token(self, token: str) -> None:
        self.content += token


@dataclass
class FakeStep:
    name: str
    type: str
    output: str = ""
    is_error: bool = False

    async def __aenter__(self) -> FakeStep:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False


class FakeServerApp:
    def __init__(self) -> None:
        self.routes: list[tuple[str, Any]] = []
        self.middlewares: list[tuple[str, Any]] = []

    def get(self, path: str):
        def decorator(func):
            self.routes.append((path, func))
            return func

        return decorator

    def middleware(self, middleware_type: str):
        def decorator(func):
            self.middlewares.append((middleware_type, func))
            return func

        return decorator


def _build_fake_chainlit_modules(
    configured_oauth_providers: list[str] | None = None,
) -> tuple[ModuleType, ModuleType, ModuleType, ModuleType]:
    fake_chainlit = ModuleType("chainlit")
    fake_chainlit.user_session = FakeUserSession()
    fake_chainlit._messages = []
    fake_chainlit._steps = []
    fake_chainlit._action_callbacks = {}
    fake_chainlit._data_layer_factory = None
    fake_chainlit._oauth_callback = None
    fake_chainlit._configured_oauth_providers = list(configured_oauth_providers or [])

    def message_factory(*args, **kwargs):
        message = FakeMessage(*args, **kwargs)
        fake_chainlit._messages.append(message)
        return message

    def step_factory(*args, **kwargs):
        step = FakeStep(*args, **kwargs)
        fake_chainlit._steps.append(step)
        return step

    def passthrough(func):
        return func

    def data_layer(func):
        fake_chainlit._data_layer_factory = func
        return func

    def oauth_callback(func):
        fake_chainlit._oauth_callback = func
        return func

    def action_callback(name: str):
        def decorator(func):
            fake_chainlit._action_callbacks[name] = func
            return func

        return decorator

    fake_chainlit.Action = FakeAction
    fake_chainlit.ChatProfile = FakeChatProfile
    fake_chainlit.Message = message_factory
    fake_chainlit.Starter = FakeStarter
    fake_chainlit.Step = step_factory
    fake_chainlit.action_callback = action_callback
    fake_chainlit.data_layer = data_layer
    fake_chainlit.oauth_callback = oauth_callback
    fake_chainlit.on_chat_end = passthrough
    fake_chainlit.on_chat_start = passthrough
    fake_chainlit.on_message = passthrough
    fake_chainlit.set_chat_profiles = passthrough
    fake_chainlit.set_starters = passthrough

    fake_server = ModuleType("chainlit.server")
    fake_server.app = FakeServerApp()

    fake_user = ModuleType("chainlit.user")
    fake_user.User = FakeUser

    fake_oauth_providers = ModuleType("chainlit.oauth_providers")

    def get_configured_oauth_providers():
        return list(fake_chainlit._configured_oauth_providers)

    fake_oauth_providers.get_configured_oauth_providers = get_configured_oauth_providers

    return fake_chainlit, fake_server, fake_user, fake_oauth_providers


def load_modules_with_fake_chainlit(
    monkeypatch,
    *module_names: str,
    configured_oauth_providers: list[str] | None = None,
):
    fake_chainlit, fake_server, fake_user, fake_oauth_providers = _build_fake_chainlit_modules(
        configured_oauth_providers
    )

    monkeypatch.setitem(sys.modules, "chainlit", fake_chainlit)
    monkeypatch.setitem(sys.modules, "chainlit.oauth_providers", fake_oauth_providers)
    monkeypatch.setitem(sys.modules, "chainlit.server", fake_server)
    monkeypatch.setitem(sys.modules, "chainlit.user", fake_user)

    imported_modules: dict[str, Any] = {}
    for module_name in module_names:
        sys.modules.pop(module_name, None)
        imported_modules[module_name] = importlib.import_module(module_name)

    return imported_modules, fake_chainlit, fake_server.app
