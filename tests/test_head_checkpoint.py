import argparse
import warnings
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import torch

from soro.routing.kev_model import SoroKevModel, load_soro_kev_checkpoint, save_soro_kev_checkpoint
from soro_boro import cli


def _make_pt_weights(model: SoroKevModel, log_temp_val: float) -> dict:
return {
"q_proj_head": model.q_proj_head.state_dict(),
"opt_proj_head": model.opt_proj_head.state_dict(),
"binary_head": model.binary_head.state_dict(),
"intent_head": model.intent_head.state_dict(),
"log_temp": torch.tensor(log_temp_val),
}


def test_load_prefers_head_safetensors(tmp_path: Path) -> None:
model = SoroKevModel(model_name="mock-a", hidden_size=16, proj_dim=8, use_mock=True, allow_mock_fallback=True)
with torch.no_grad():
model.log_temp.fill_(1.0)
save_soro_kev_checkpoint(model, tmp_path)
torch.save(_make_pt_weights(model, 2.5), tmp_path / "head.pt")

with warnings.catch_warnings(record=True) as caught:
warnings.simplefilter("always")
loaded, _, _ = load_soro_kev_checkpoint(tmp_path, device="cpu")
assert not any(issubclass(w.category, UserWarning) for w in caught)
assert torch.allclose(loaded.log_temp, torch.tensor(1.0))


def test_load_falls_back_to_head_pt_with_warning(tmp_path: Path) -> None:
model = SoroKevModel(model_name="mock-a", hidden_size=16, proj_dim=8, use_mock=True, allow_mock_fallback=True)
save_soro_kev_checkpoint(model, tmp_path)
(tmp_path / "head.safetensors").unlink(missing_ok=True)
torch.save(_make_pt_weights(model, 2.5), tmp_path / "head.pt")

with pytest.warns(UserWarning):
load_soro_kev_checkpoint(tmp_path, device="cpu")


def test_doctor_warns_when_only_head_pt_present(tmp_path: Path, capsys) -> None:
only_pt = tmp_path / "only_pt"
only_pt.mkdir()
(only_pt / "head.pt").write_bytes(b"")

both = tmp_path / "both"
both.mkdir()
(both / "head.pt").write_bytes(b"")
(both / "head.safetensors").write_bytes(b"")

fake_router = SimpleNamespace(backend="mock", q_hat=0.5)
with patch.object(cli.Router, "from_pretrained", return_value=fake_router):
cli.cmd_doctor(argparse.Namespace(model=str(only_pt), device="cpu", check_model=True))
out_warn = capsys.readouterr().out
assert "WARN" in out_warn
assert "convert-head" in out_warn

cli.cmd_doctor(argparse.Namespace(model=str(both), device="cpu", check_model=True))
out_ok = capsys.readouterr().out
assert "WARN" not in out_ok
