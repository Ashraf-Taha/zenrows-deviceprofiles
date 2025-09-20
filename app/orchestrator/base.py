from abc import ABC, abstractmethod
from typing import Generic, TypeVar

Req = TypeVar("Req")
Res = TypeVar("Res")


class BaseValidator(ABC, Generic[Req]):
    @abstractmethod
    def validate(self, request: Req) -> None:
        ...


class BaseRequestTransformer(ABC, Generic[Req]):
    @abstractmethod
    def transform(self, request: Req) -> Req:
        ...


class BaseExecutor(ABC, Generic[Req, Res]):
    @abstractmethod
    def execute(self, request: Req) -> Res:
        ...


class BaseResponseTransformer(ABC, Generic[Res]):
    @abstractmethod
    def transform(self, response: Res) -> Res:
        ...
