#!/usr/bin/env python3
"""Offline version-specific vLLM wiring regression, run with the isolated serving Python.

Loads only a local tokenizer. Never constructs an engine, loads weights, or generates.
This supplements repository tests; it is not GPU/server acceptance.
"""

import argparse
import importlib.metadata
import json
import os
import socket
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
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
    version = importlib.metadata.version("vllm")
    assert version in {"0.10.2", "0.19.0"}
    if version == "0.19.0":
        os.environ.pop("VLLM_ATTENTION_BACKEND", None)
        os.environ.pop("VLLM_USE_V1", None)
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

        tokenizer = AutoTokenizer.from_pretrained(
            args.snapshot,
            local_files_only=True,
            trust_remote_code=False,
        )
        vocab_size = json.loads((args.snapshot / "config.json").read_bytes())["vocab_size"]
        if version == "0.10.2":
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
        else:
            from vllm.config import StructuredOutputsConfig
            from vllm.engine.arg_utils import EngineArgs
            from vllm.entrypoints.openai.chat_completion.protocol import ChatCompletionRequest
            from vllm.utils.argparse_utils import FlexibleArgumentParser
            from vllm.v1.request import Request
            from vllm.v1.structured_output import StructuredOutputManager

            cli = EngineArgs.add_cli_args(FlexibleArgumentParser())
            engine_args = EngineArgs.from_cli_args(
                cli.parse_args(
                    [
                        "--model",
                        str(args.snapshot),
                        "--dtype",
                        "float16",
                        "--attention-backend",
                        "TRITON_ATTN",
                        "--structured-outputs-config.backend",
                        "xgrammar",
                    ]
                )
            )
            assert engine_args.attention_backend == "TRITON_ATTN"
            assert engine_args.structured_outputs_config.backend == "xgrammar"
            parsed = ChatCompletionRequest.model_validate(body)
            params = parsed.to_sampling_params(512, {})
            assert params.structured_outputs.json == schema
            settings = StructuredOutputsConfig(backend="xgrammar")
            params._validate_structured_outputs(settings, tokenizer)
            assert params.structured_outputs._backend == "xgrammar"
            assert not params.structured_outputs._backend_was_auto
            # SamplingParams.clone shares StructuredOutputsParams in 0.19.
            # Isolate this negative control from the actual F grammar below.
            unsupported = deepcopy(params)
            unsupported.structured_outputs.json = {"type": "array", "uniqueItems": True}
            try:
                unsupported._validate_structured_outputs(settings, tokenizer)
            except ValueError as error:
                assert "not supported by xgrammar" in str(error)
            else:
                raise AssertionError("unsupported schema did not fail closed")
            assert unsupported.structured_outputs._backend == "xgrammar"
            assert not unsupported.structured_outputs._backend_was_auto
            # Compiler rejection must propagate, never select a fallback backend.
            with patch(
                "vllm.v1.structured_output.backend_xgrammar.validate_xgrammar_grammar",
                side_effect=ValueError("synthetic unsupported grammar"),
            ):
                try:
                    params.clone()._validate_structured_outputs(settings, tokenizer)
                except ValueError as error:
                    assert str(error) == "synthetic unsupported grammar"
                else:
                    raise AssertionError("compiler failure did not propagate")
            request = Request("offline", [1], params, None)
            assert request.structured_output_request is not None
            manager = StructuredOutputManager.__new__(StructuredOutputManager)
            manager.vllm_config = SimpleNamespace(
                model_config=SimpleNamespace(get_vocab_size=lambda: vocab_size),
                structured_outputs_config=settings,
                speculative_config=None,
            )
            manager.tokenizer, manager.backend = tokenizer, None
            manager._use_async_grammar_compilation = False
            manager.grammar_init(request)
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
                "vllm": version,
                "xgrammar": importlib.metadata.version("xgrammar"),
                "schema_preserved": True,
                "v0_unenforced_control": version == "0.10.2",
                "explicit_backend_no_fallback": version == "0.19.0",
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
