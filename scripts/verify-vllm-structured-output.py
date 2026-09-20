#!/usr/bin/env python3
"""Offline vLLM 0.10.2 wiring regression, run with the isolated serving Python.

Loads only a local tokenizer. Never constructs an engine, loads weights, or generates.
This supplements repository tests; it is not GPU/server acceptance.
"""

import argparse
import importlib.metadata
import json
import os
import socket
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


def blocked(*args, **kwargs):
    raise AssertionError("Network/model dispatch prohibited")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--request", type=Path, help="Optional saved outbound JSON body")
    args = parser.parse_args()
    os.environ.update(
        HF_HUB_OFFLINE="1",
        TRANSFORMERS_OFFLINE="1",
        HF_HUB_DISABLE_TELEMETRY="1",
        VLLM_NO_USAGE_STATS="1",
        DO_NOT_TRACK="1",
        VLLM_USE_V1="1",
        VLLM_ATTENTION_BACKEND="XFORMERS_VLLM_V1",
    )
    assert importlib.metadata.version("vllm") == "0.10.2"
    root = Path(__file__).resolve().parents[1]
    schema = json.loads((root / "prompts/extraction/v1/decompose.output.schema.json").read_bytes())
    body = (
        json.loads(args.request.read_bytes())
        if args.request
        else {
            "model": "synthetic-offline-only",
            "messages": [{"role": "user", "content": "Synthetic offline schema check"}],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "t04_f",
                    "strict": True,
                    "schema": schema,
                },
            },
            "max_tokens": 512,
        }
    )
    assert body["response_format"]["json_schema"]["schema"] == schema
    with (
        patch.object(socket, "create_connection", blocked),
        patch.object(socket.socket, "connect", blocked),
        patch.object(socket.socket, "connect_ex", blocked),
        patch.object(socket, "getaddrinfo", blocked),
    ):
        import torch
        import xgrammar
        from transformers import AutoTokenizer

        # Capture the V0 class before its module aliases LLMEngine to V1.
        os.environ["VLLM_USE_V1"] = "0"
        from vllm.engine.llm_engine import LLMEngine

        os.environ["VLLM_USE_V1"] = "1"
        from vllm.entrypoints.openai.protocol import ChatCompletionRequest
        from vllm.v1.request import Request
        from vllm.v1.structured_output import StructuredOutputManager
        from vllm.v1.structured_output.backend_xgrammar import validate_xgrammar_grammar

        parsed = ChatCompletionRequest.model_validate(body)
        params = parsed.to_sampling_params(512, None, {})
        assert params.guided_decoding.json == schema
        # Negative control: the historical V0 path silently installs no enforcement.
        old = LLMEngine._build_logits_processors(SimpleNamespace(), params.clone(), None)
        assert not old.logits_processors
        params.guided_decoding.backend = "xgrammar"
        validate_xgrammar_grammar(params)
        tokenizer = AutoTokenizer.from_pretrained(
            args.snapshot,
            local_files_only=True,
            trust_remote_code=False,
        )
        vocab_size = json.loads((args.snapshot / "config.json").read_bytes())["vocab_size"]
        config = SimpleNamespace(
            decoding_config=SimpleNamespace(disable_any_whitespace=False),
            speculative_config=None,
            model_config=SimpleNamespace(get_vocab_size=lambda: vocab_size),
        )
        # Exercise the actual V1 request and grammar wiring without a model engine.
        request = Request.from_engine_core_request(
            SimpleNamespace(
                request_id="offline",
                client_index=0,
                prompt_token_ids=[1],
                mm_features=None,
                sampling_params=params,
                pooling_params=None,
                eos_token_id=tokenizer.eos_token_id,
                arrival_time=0,
                lora_request=None,
                cache_salt=None,
                priority=0,
                trace_headers=None,
            ),
            None,
        )
        assert request.use_structured_output and request.structured_output_request is not None
        manager = StructuredOutputManager.__new__(StructuredOutputManager)
        manager.vllm_config, manager.tokenizer, manager.backend = config, tokenizer, None
        with ThreadPoolExecutor(max_workers=1) as executor:
            manager.executor = executor
            manager.grammar_init(request)
            request.structured_output_request._grammar.result(timeout=60)
        grammar = request.structured_output_request.grammar
        assert grammar is not None and manager.backend is not None
        # Verify enforcement, not merely compiler acceptance: mask synthetic logits.
        mask = manager.backend.allocate_token_bitmask(1)
        grammar.fill_bitmask(mask, 0)
        logits = torch.zeros((1, vocab_size), dtype=torch.float32)
        xgrammar.apply_token_bitmask_inplace(logits, mask)
        assert torch.isneginf(logits).any() and torch.isfinite(logits).any()
        malformed = (
            '{"candidates":[{"text":"Rot.","anchor":"Rot.","required_support":[],'
            '"consumed_binding_indices":[]}],"reason_code":"none"}'
        )
        assert not grammar.matcher.accept_string(malformed)
        grammar.reset()
        # Independent schema-conforming control; never a replacement for saved output.
        assert grammar.matcher.accept_string(
            '{"candidates":[],"reason_code":"cannot_extract","status":"unresolved"}'
        )
    print(
        json.dumps(
            {
                "status": "passed",
                "vllm": "0.10.2",
                "xgrammar": importlib.metadata.version("xgrammar"),
                "schema_preserved": True,
                "v0_unenforced_control": True,
                "v1_grammar_attached": True,
                "invalid_tokens_masked": True,
                "malformed_shape_rejected": True,
                "model_calls": 0,
                "network_blocked": True,
                "gpu_serving_verified": False,
            }
        )
    )


if __name__ == "__main__":
    main()
