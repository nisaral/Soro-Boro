"""Tests for Soro-Kev sequence packing and mini-batched forward passes."""

import pytest
import torch

from soro.routing.kev_model import SoroKevModel, MockCausalBackbone


@pytest.fixture
def mock_kev_model():
    return SoroKevModel(use_mock=True)


def test_forward_batch_matches_single_item_inference(mock_kev_model):
    """Verify that forward_batch produces the exact same logits as batch_size=1 forward pass."""
    mock_kev_model.eval()

    item_a = {
        "id": "item_a",
        "state": "User Request: Read customer billing records from storage",
        "questions": {
            "tool_route": {
                "type": "choice",
                "instructions": "Which tool?",
                "criteria": {
                    "read_records": "Read customer records",
                    "write_records": "Write customer records",
                    "delete_records": "Delete customer records",
                    "__abstain__": "None of the above",
                },
                "label": "read_records",
            },
            "tool_route_perm": {
                "type": "choice",
                "instructions": "Which tool?",
                "criteria": {
                    "__abstain__": "None of the above",
                    "delete_records": "Delete customer records",
                    "write_records": "Write customer records",
                    "read_records": "Read customer records",
                },
                "label": "read_records",
            },
            "arg_mapping": {
                "type": "choice",
                "instructions": "Target parameter?",
                "criteria": {"record_id": "Record ID", "limit": "Limit", "__drop__": "Drop"},
                "label": "record_id",
            },
            "missing_required": {"type": "noul", "instructions": "Missing?", "label": "no"},
            "is_mutation": {"type": "noul", "instructions": "Mutation?", "label": "no"},
        },
    }

    item_b = {
        "id": "item_b",
        "state": "User Request: Permanently drop the staging database schema",
        "questions": {
            "tool_route": {
                "type": "choice",
                "instructions": "Which tool?",
                "criteria": {
                    "drop_schema": "Drop database schema",
                    "query_schema": "Inspect schema",
                    "alter_table": "Alter table",
                    "create_index": "Create index",
                    "__abstain__": "None",
                },
                "label": "drop_schema",
            },
            "tool_route_perm": {
                "type": "choice",
                "instructions": "Which tool?",
                "criteria": {
                    "__abstain__": "None",
                    "create_index": "Create index",
                    "alter_table": "Alter table",
                    "query_schema": "Inspect schema",
                    "drop_schema": "Drop database schema",
                },
                "label": "drop_schema",
            },
            "arg_mapping": {
                "type": "choice",
                "instructions": "Target parameter?",
                "criteria": {"schema_name": "Schema Name", "__drop__": "Drop"},
                "label": "schema_name",
            },
            "missing_required": {"type": "noul", "instructions": "Missing?", "label": "no"},
            "is_mutation": {"type": "noul", "instructions": "Mutation?", "label": "yes"},
        },
    }

    with torch.no_grad():
        out_single_a = mock_kev_model.forward_batch([item_a])
        logits_single_a = out_single_a["logits_route_batch"][0]

        out_single_b = mock_kev_model.forward_batch([item_b])
        logits_single_b = out_single_b["logits_route_batch"][0]

        out_batch = mock_kev_model.forward_batch([item_a, item_b])
        logits_batch_a = out_batch["logits_route_batch"][0]
        logits_batch_b = out_batch["logits_route_batch"][1]

    # Verify zero discrepancy across batching padding
    diff_a = torch.max(torch.abs(logits_single_a - logits_batch_a)).item()
    diff_b = torch.max(torch.abs(logits_single_b - logits_batch_b)).item()

    assert diff_a < 1e-4, f"Discrepancy for item A too high: {diff_a}"
    assert diff_b < 1e-4, f"Discrepancy for item B too high: {diff_b}"


def test_forward_batch_backward_gradients(mock_kev_model):
    """Verify that batched forward pass computes non-zero gradients for all heads."""
    mock_kev_model.train()
    optimizer = torch.optim.AdamW(mock_kev_model.parameters(), lr=1e-3)
    optimizer.zero_grad()

    item = {
        "id": "grad_test",
        "state": "User Request: Send email to auditor",
        "questions": {
            "tool_route": {
                "type": "choice",
                "instructions": "Which tool?",
                "criteria": {"send_email": "Send email", "read_email": "Read email", "__abstain__": "Abstain"},
                "label": "send_email",
            },
            "tool_route_perm": {
                "type": "choice",
                "instructions": "Which tool?",
                "criteria": {"__abstain__": "Abstain", "read_email": "Read email", "send_email": "Send email"},
                "label": "send_email",
            },
            "arg_mapping": {
                "type": "choice",
                "instructions": "Target parameter?",
                "criteria": {"recipient": "Recipient", "__drop__": "Drop"},
                "label": "recipient",
            },
            "missing_required": {"type": "noul", "instructions": "Missing?", "label": "no"},
            "is_mutation": {"type": "noul", "instructions": "Mutation?", "label": "yes"},
        },
    }

    out = mock_kev_model.forward_batch([item, item])
    loss = out["loss"]
    assert loss.item() > 0.0
    loss.backward()

    # Verify gradients on pointer projection heads
    assert mock_kev_model.q_proj_head.weight.grad is not None
    assert torch.sum(torch.abs(mock_kev_model.q_proj_head.weight.grad)).item() > 0.0
    assert mock_kev_model.opt_proj_head.weight.grad is not None
    assert torch.sum(torch.abs(mock_kev_model.opt_proj_head.weight.grad)).item() > 0.0
    assert mock_kev_model.binary_head.weight.grad is not None
    assert torch.sum(torch.abs(mock_kev_model.binary_head.weight.grad)).item() > 0.0
