"""The Python sidecar: HarnessService + DecisionService on one port.

    veyra-py serve --addr 127.0.0.1:7777 --decision heuristic

The kernel dials this process. One process, one port, one place to look when
something is wrong.
"""

from __future__ import annotations

import argparse
import logging
import signal
from concurrent import futures
from typing import Any

import grpc

from soro.contract import parse_options
from soro.decision import BACKENDS, get_backend
from soro.harness.base import HarnessAdapter
from soro.harness.registry import HarnessRegistry
from soro.v1 import runtime_pb2 as pb
from soro.v1 import runtime_pb2_grpc as pb_grpc

log = logging.getLogger("soro.server")


class HarnessService(pb_grpc.HarnessServiceServicer):
    def __init__(self, registry: HarnessRegistry, base_opts: dict[str, Any] | None = None):
        self.registry = registry
        self.base_opts = dict(base_opts or {})
        self.sessions: dict[str, dict[str, HarnessAdapter]] = {}

    # -- helpers -----------------------------------------------------------

    def _session_key(self, run_id: str, task_id: str) -> str:
        return run_id or f"anon:{task_id}"

    def _adapter(self, key: str, harness_id: str) -> HarnessAdapter:
        session = self.sessions.get(key)
        if not session:
            raise KeyError(f"no harness session for run {key!r}")
        adapter = session.get(harness_id)
        if adapter is None:
            if len(session) == 1:
                return next(iter(session.values()))
            raise KeyError(f"run {key!r} has no harness {harness_id!r}")
        return adapter

    # -- rpc ---------------------------------------------------------------

    def Start(self, request: pb.StartRequest, context) -> pb.StartResponse:
        task = request.task
        opts = {**self.base_opts, **parse_options(request.options_json)}
        if task.workspace and "workspace" not in opts:
            opts["workspace"] = task.workspace
        key = self._session_key(request.run_id, task.id)
        try:
            adapter = self.registry.create(request.harness_id, opts)
        except Exception as exc:
            context.abort(grpc.StatusCode.FAILED_PRECONDITION, f"cannot create harness {request.harness_id!r}: {exc}")
        resumed = request.state if request.state and request.state.task_id else None
        state = adapter.start(task, resumed)
        self.sessions.setdefault(key, {})[request.harness_id] = adapter
        log.info("start %s run=%s harness=%s resumed=%s", task.id, key, request.harness_id, bool(resumed))
        return pb.StartResponse(run_id=key, state=state)

    def Step(self, request: pb.StepRequest, context) -> pb.StepResponse:
        state = request.state
        try:
            adapter = self._adapter(request.run_id, state.harness_id)
        except KeyError as exc:
            context.abort(grpc.StatusCode.NOT_FOUND, str(exc))
        try:
            new_state = adapter.step(state, request.decision)
        except Exception as exc:
            log.exception("harness step failed")
            context.abort(grpc.StatusCode.INTERNAL, f"harness step failed: {exc}")
        return pb.StepResponse(state=new_state, needs_decision=not new_state.done)

    def Control(self, request: pb.ControlRequest, context) -> pb.ControlResponse:
        session = self.sessions.get(request.run_id, {})
        adapter = session.get(request.harness_id)
        if adapter is None and len(session) == 1:
            adapter = next(iter(session.values()))
        if adapter is None:
            return pb.ControlResponse(ok=False, error=f"no session for {request.run_id!r}")
        try:
            adapter.control(request.op)
        except Exception as exc:
            return pb.ControlResponse(ok=False, error=str(exc))
        if request.op in (pb.INTERRUPT, pb.TERMINATE_RUN):
            session.pop(request.harness_id, None)
        return pb.ControlResponse(ok=True)

    def Inspect(self, request: pb.InspectRequest, context) -> pb.InspectResponse:
        session = self.sessions.get(request.run_id, {})
        adapter = session.get(request.harness_id) or (next(iter(session.values())) if session else None)
        if adapter is None:
            return pb.InspectResponse(alive=False, harness_meta_json="{}")
        state = adapter.inspect()
        return pb.InspectResponse(state=state, alive=True, harness_meta_json="{}")

    def ListHarnesses(self, request: pb.ListHarnessesRequest, context) -> pb.ListHarnessesResponse:
        return pb.ListHarnessesResponse(harnesses=self.registry.infos())


class DecisionService(pb_grpc.DecisionServiceServicer):
    def __init__(self, default_backend: str = "heuristic", opts: dict[str, Any] | None = None):
        self.default_backend = default_backend
        self.opts = dict(opts or {})
        self.cache: dict[str, Any] = {}

    def _model(self, requested: str):
        name = requested or self.default_backend
        if name not in self.cache:
            self.cache[name] = get_backend(name, **self.opts)
        return self.cache[name]

    def Decide(self, request: pb.DecisionRequest, context) -> pb.Decision:
        from soro.decision.base import decide

        try:
            model = self._model(request.backend)
        except KeyError as exc:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        try:
            return decide(model, request, list(request.candidates), {})
        except Exception as exc:
            # The kernel treats this as a soft failure and falls back to its own
            # heuristic, recording `decision_fallback` in the event log.
            context.abort(grpc.StatusCode.UNAVAILABLE, f"decision backend {model.name} failed: {exc}")


def build_server(addr: str, harness_opts: dict[str, Any] | None = None,
                 default_backend: str = "heuristic", decision_opts: dict[str, Any] | None = None,
                 workers: int = 8) -> tuple[grpc.Server, HarnessService]:
    registry = HarnessRegistry(harness_opts)
    harness_service = HarnessService(registry, harness_opts)
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=workers))
    pb_grpc.add_HarnessServiceServicer_to_server(harness_service, server)
    pb_grpc.add_DecisionServiceServicer_to_server(DecisionService(default_backend, decision_opts), server)
    server.add_insecure_port(addr)
    log.info("listening on %s (default backend=%s)", addr, default_backend)
    return server, harness_service


def serve(addr: str, harness_opts: dict[str, Any] | None = None, default_backend: str = "heuristic",
          decision_opts: dict[str, Any] | None = None) -> None:
    server, _ = build_server(addr, harness_opts, default_backend, decision_opts)
    server.start()

    stop = signal.Event() if hasattr(signal, "Event") else None
    import threading

    done = threading.Event()

    def _handle(signum, frame):
        log.info("signal %s: shutting down", signum)
        server.stop(grace=2.0)
        done.set()

    for sig in (signal.SIGINT, getattr(signal, "SIGTERM", signal.SIGINT)):
        try:
            signal.signal(sig, _handle)
        except (ValueError, OSError):
            pass

    print(f"veyra-py listening on {addr}  decision={default_backend}  harnesses={[i['id'] for i in HarnessRegistry(harness_opts).triage()]}", flush=True)
    _ = stop
    done.wait()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="veyra-py", description="Veyra Python sidecar")
    parser.add_argument("--addr", default="127.0.0.1:7777")
    parser.add_argument("--decision", default="heuristic", choices=sorted(BACKENDS) + ["von-surrogate"])
    parser.add_argument("--workspace", default="")
    parser.add_argument("--allow-shell", action="store_true", default=True)
    parser.add_argument("--no-shell", dest="allow_shell", action="store_false")
    parser.add_argument("--von-endpoint", default="")
    parser.add_argument("--bandit-state", default="")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    backend = "von" if args.decision == "von-surrogate" else args.decision
    serve(
        args.addr,
        harness_opts={"workspace": args.workspace} if args.workspace else {},
        default_backend=backend,
        decision_opts={"endpoint": args.von_endpoint or None, "state_path": args.bandit_state or None},
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())