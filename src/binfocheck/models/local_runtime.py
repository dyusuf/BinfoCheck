"""Live-only capability guard; legacy preparation and replay stay byte-identical."""

from .config import MODELS, LocalGenerationConfig
from .errors import ModelError
from .json import digest, object_value, parse


def require_structured_runtime(config: LocalGenerationConfig, manifest: bytes) -> None:
    if config.version != "2" or config.engine != "V1":
        raise ModelError("local_structured_output_unavailable")
    if digest(manifest) != config.runtime_manifest_sha256:
        raise ModelError("local_runtime_manifest_mismatch")
    data = object_value(parse(manifest))
    env = object_value(data.get("environment"))
    server = object_value(data.get("server_version"))
    args = data.get("launch_arguments")
    if (
        data.get("model") != MODELS["vllm"]
        or server.get("version") != config.server_version
        or env.get("VLLM_USE_V1") != "1"
        or env.get("VLLM_ATTENTION_BACKEND") != config.attention_backend
        or env.get("HF_HUB_OFFLINE") != "1"
        or env.get("TRANSFORMERS_OFFLINE") != "1"
        or not isinstance(args, list)
        or not all(isinstance(arg, str) for arg in args)
    ):
        raise ModelError("local_runtime_settings_mismatch")
    for flag, value in (
        ("--guided-decoding-backend", "xgrammar"),
        ("--dtype", config.dtype),
        ("--served-model-name", MODELS["vllm"]),
        ("--max-model-len", str(config.max_model_len)),
    ):
        if args.count(flag) != 1 or any(str(arg).startswith(flag + "=") for arg in args):
            raise ModelError("local_runtime_settings_mismatch")
        index = args.index(flag)
        if index + 1 >= len(args) or args[index + 1] != value:
            raise ModelError("local_runtime_settings_mismatch")
    flag = "--guided-decoding-disable-fallback"
    if args.count(flag) != 1 or any(str(arg).startswith(flag + "=") for arg in args):
        raise ModelError("local_runtime_settings_mismatch")
