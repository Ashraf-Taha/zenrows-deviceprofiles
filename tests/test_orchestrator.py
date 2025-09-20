from app.orchestrator.base import (
    BaseExecutor,
    BaseRequestTransformer,
    BaseResponseTransformer,
    BaseValidator,
)
from app.orchestrator.orchestrator import PipelineOrchestrator


class V(BaseValidator[dict]):
    def validate(self, request: dict) -> None:
        if "ok" not in request:
            raise ValueError("invalid")


class RT(BaseRequestTransformer[dict]):
    def transform(self, request: dict) -> dict:
        x = dict(request)
        x["t"] = True
        return x


class E(BaseExecutor[dict, dict]):
    def execute(self, request: dict) -> dict:
        return {"done": request.get("t", False)}


class R(BaseResponseTransformer[dict]):
    def transform(self, response: dict) -> dict:
        y = dict(response)
        y["post"] = 1
        return y


def test_given_validators_and_steps_when_run_then_pipeline_applies_all():
    orch = PipelineOrchestrator[dict, dict](
        validators=[V()],
        request_transformers=[RT()],
        executors=[E()],
        response_transformers=[R()],
    )
    out = orch.run({"ok": 1})
    assert out == {"done": True, "post": 1}


def test_given_missing_ok_when_validate_then_raises():
    orch = PipelineOrchestrator[dict, dict](validators=[V()], executors=[E()])
    try:
        orch.run({})
        assert False
    except ValueError as e:
        assert str(e) == "invalid"


def test_given_no_executors_when_run_then_error():
    orch = PipelineOrchestrator[dict, dict]()
    try:
        orch.run({})
        assert False
    except RuntimeError as e:
        assert str(e) == "No executors configured"


class NoneExec(BaseExecutor[dict, dict]):
    def execute(self, request: dict) -> dict:  # type: ignore[return-value]
        return None  # type: ignore[return-value]


def test_given_none_result_when_execute_then_error():
    orch = PipelineOrchestrator[dict, dict](executors=[NoneExec()])
    try:
        orch.run({})
        assert False
    except RuntimeError as e:
        assert str(e) == "Execution produced no result"
