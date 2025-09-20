from typing import Iterable, List, Generic, TypeVar

from app.orchestrator.base import (
    BaseExecutor,
    BaseRequestTransformer,
    BaseResponseTransformer,
    BaseValidator,
)

Req = TypeVar("Req")
Res = TypeVar("Res")


class PipelineOrchestrator(Generic[Req, Res]):
    def __init__(
        self,
        validators: Iterable[BaseValidator[Req]] | None = None,
        request_transformers: Iterable[BaseRequestTransformer[Req]] | None = None,
        executors: Iterable[BaseExecutor[Req, Res]] | None = None,
        response_transformers: Iterable[BaseResponseTransformer[Res]] | None = None,
    ) -> None:
        self.validators: List[BaseValidator[Req]] = list(validators or [])
        self.request_transformers: List[BaseRequestTransformer[Req]] = list(
            request_transformers or []
        )
        self.executors: List[BaseExecutor[Req, Res]] = list(executors or [])
        self.response_transformers: List[BaseResponseTransformer[Res]] = list(
            response_transformers or []
        )

    def run(self, request: Req) -> Res:
        for v in self.validators:
            v.validate(request)
        current = request
        for t in self.request_transformers:
            current = t.transform(current)
        if not self.executors:
            raise RuntimeError("No executors configured")
        result: Res | None = None
        for e in self.executors:
            result = e.execute(current)
        if result is None:
            raise RuntimeError("Execution produced no result")
        for rt in self.response_transformers:
            result = rt.transform(result)
        return result
