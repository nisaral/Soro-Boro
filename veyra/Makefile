# Veyra: Go kernel + Python harness/decision plane.
#
# POSIX targets (Linux/macOS/WSL) so CI and local contributors run the same
# commands. On Windows each target is a one-liner; see README.md "Quickstart".

SHELL     := /bin/sh
GO        ?= go
PY        ?= python3
PROTOC    ?= protoc
MODULE    := github.com/nisaral/veyra
DIST      := dist
KERNEL    := $(DIST)/veyra
BANDIT    := policies/bandit.json

export PYTHONPATH := python/src:$(PYTHONPATH)

.PHONY: help build proto proto-check test test-go test-py lint fmt bench-dev bench-test train doctor clean

help:
	@echo "targets:"
	@echo "  build        compile the Go kernel to $(KERNEL)"
	@echo "  proto        regenerate Go + Python wire format from proto/"
	@echo "  proto-check  regenerate and fail if the committed output differs"
	@echo "  test         go test + pytest"
	@echo "  lint         go vet"
	@echo "  bench-dev    dev split, all arms                 -> out/dev"
	@echo "  train        fit the bandit on dev traces only   -> $(BANDIT)"
	@echo "  bench-test   held-out split + pre-registered verdict -> out/test"
	@echo "  doctor       environment + harness + backend check"
	@echo "  clean        remove build and run artifacts"

build:
	@mkdir -p $(DIST)
	cd go && $(GO) build -o ../$(KERNEL) ./cmd/veyra

proto:
	$(PROTOC) -I proto --go_out=go --go_opt=module=$(MODULE) \
	  --go-grpc_out=go --go-grpc_opt=module=$(MODULE) proto/veyra/v1/runtime.proto
	$(PY) -m grpc_tools.protoc -I proto --python_out=python/src --pyi_out=python/src \
	  --grpc_python_out=python/src proto/veyra/v1/runtime.proto

proto-check: proto
	git diff --exit-code -- go/gen python/src/veyra/v1

test: test-go test-py

test-go:
	cd go && $(GO) test ./internal/...

test-py:
	cd python && $(PY) -m pytest -q

lint:
	cd go && $(GO) vet ./internal/... ./cmd/...

fmt:
	cd go && $(GO) fmt ./...

bench-dev: build
	$(PY) -m veyra.cli compare --spawn --split dev --out out/dev
	@echo "next: make train && make bench-test"

train:
	$(PY) -m veyra.cli train --runs-dir out/dev/runs --out $(BANDIT)

bench-test: build
	$(PY) -m veyra.cli compare --spawn --split test --out out/test \
	  --select-from out/dev --bandit-state $(BANDIT)

doctor:
	$(PY) -m veyra.cli doctor

clean:
	rm -rf $(DIST) out .pytest_cache
