"""
Free AI Model Router
Unified OpenAI-compatible API across free providers with failover.
"""
import json
import os
import urllib.request
import urllib.error
from typing import Optional

# Provider definitions: base_url + env var + free model hints
PROVIDERS = [
    {
        "id": "github",
        "name": "GitHub Models",
        "base_url": "https://models.github.ai/inference",
        "env_key": "GITHUB_TOKEN",
        "models": ["openai/gpt-4o", "meta-llama/llama-3.3-70b-instruct", "microsoft/phi-4"],
        "free": True,
        "note": "Uses GitHub PAT; rate-limited free tier"
    },
    {
        "id": "openrouter",
        "name": "OpenRouter Free",
        "base_url": "https://openrouter.ai/api/v1",
        "env_key": "OPENROUTER_API_KEY",
        "models": ["meta-llama/llama-3.3-70b-instruct:free", "google/gemma-2-9b-it:free", "mistralai/mistral-7b-instruct:free"],
        "free": True,
        "note": "22+ free models with :free suffix"
    },
    {
        "id": "groq",
        "name": "Groq Free",
        "base_url": "https://api.groq.com/openai/v1",
        "env_key": "GROQ_API_KEY",
        "models": ["llama-3.3-70b-versatile", "gemma2-9b-it", "mistral-saba-7b-instruct"],
        "free": True,
        "note": "Ultra-fast inference, generous daily limits"
    },
    {
        "id": "google",
        "name": "Google AI Studio",
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "env_key": "GOOGLE_AI_API_KEY",
        "models": ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-pro"],
        "free": True,
        "note": "Most generous free tier, 15 free models"
    },
    {
        "id": "huggingface",
        "name": "Hugging Face",
        "base_url": "https://router.huggingface.co/v1",
        "env_key": "HUGGINGFACE_TOKEN",
        "models": ["meta-llama/Llama-3.3-70B-Instruct", "mistralai/Mistral-7B-Instruct-v0.3"],
        "free": True,
        "note": "Free tier for community models"
    },
    {
        "id": "together",
        "name": "Together AI",
        "base_url": "https://api.together.xyz/v1",
        "env_key": "TOGETHER_API_KEY",
        "models": ["meta-llama/Llama-3.3-70B-Instruct-Turbo", "mistralai/Mixtral-8x7B-Instruct-v0.1"],
        "free": True,
        "note": "71 free models, fast inference"
    },
    {
        "id": "cerebras",
        "name": "Cerebras",
        "base_url": "https://api.cerebras.ai/v1",
        "env_key": "CEREBRAS_API_KEY",
        "models": ["llama-3.3-70b", "gemma-2-9b-it"],
        "free": True,
        "note": "8 free models, no credit card"
    },
    {
        "id": "cloudflare",
        "name": "Cloudflare Workers AI",
        "base_url": "https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run",
        "env_key": "CLOUDFLARE_ACCOUNT_ID",
        "models": ["llama-3.3-70b-instruct", "gemma-2-9b-it"],
        "free": True,
        "note": "39 free models, 10K neurons/day"
    },
    {
        "id": "mistral",
        "name": "Mistral AI",
        "base_url": "https://api.mistral.ai/v1",
        "env_key": "MISTRAL_API_KEY",
        "models": ["mistral-large-latest", "codestral-latest", "mistral-nemo"],
        "free": True,
        "note": "12 free models, 1 req/s"
    },
    {
        "id": "ollama",
        "name": "Ollama Local",
        "base_url": "http://localhost:11434/v1",
        "env_key": None,
        "models": ["deepseek-r1:7b", "deepseek-hermes:7b", "qwen2.5:7b"],
        "free": True,
        "note": "Unlimited local inference, no API key"
    },
    {
        "id": "nvidia_nim",
        "name": "NVIDIA NIM",
        "base_url": "https://integrate.api.nvidia.com/v1",
        "env_key": "NVIDIA_API_KEY",
        "models": ["meta/llama-3.3-70b-instruct", "nvidia/nemotron-3-8b-instruct"],
        "free": True,
        "note": "123 free models, accelerated inference"
    },
    {
        "id": "siliconflow",
        "name": "SiliconFlow",
        "base_url": "https://api.siliconflow.cn/v1",
        "env_key": "SILICONFLOW_API_KEY",
        "models": ["deepseek-ai/DeepSeek-V3", "Qwen/Qwen2.5-72B-Instruct"],
        "free": True,
        "note": "3 free models, rising platform"
    },
    {
        "id": "deepseek",
        "name": "DeepSeek Platform",
        "base_url": "https://api.deepseek.com/v1",
        "env_key": "DEEPSEEK_API_KEY",
        "models": ["deepseek-chat", "deepseek-reasoner"],
        "free": True,
        "note": "5M tokens free for new users"
    },
    {
        "id": "openai_compat",
        "name": "OpenAI-Compatible Proxy",
        "base_url": "http://localhost:8000/v1",
        "env_key": None,
        "models": ["auto"],
        "free": True,
        "note": "Local proxy if running one"
    }
]

def get_provider_catalog():
    return {
        "total_providers": len(PROVIDERS),
        "providers": [
            {
                "id": p["id"],
                "name": p["name"],
                "base_url": p["base_url"],
                "models": p["models"],
                "free": p["free"],
                "note": p["note"]
            }
            for p in PROVIDERS
        ]
    }

def _has_key(env_key: Optional[str]) -> bool:
    if not env_key:
        return False
    return bool(os.environ.get(env_key))

def _call_openai_compatible(base_url: str, model: str, messages: list, api_key: Optional[str] = None, path: str = "/chat/completions") -> dict:
    url = base_url.rstrip("/") + path
    payload = json.dumps({"model": model, "messages": messages}).encode()
    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("Content-Type", "application/json")
    if api_key:
        req.add_header("Authorization", f"Bearer {api_key}")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}", "body": e.read().decode()[:500]}
    except Exception as e:
        return {"error": str(e)}

def chat_completions(messages: list, model: Optional[str] = None, provider_id: Optional[str] = None) -> dict:
    """Try providers in order, return first successful result."""
    tried = []

    # If specific provider requested
    if provider_id:
        for p in PROVIDERS:
            if p["id"] == provider_id:
                api_key = os.environ.get(p["env_key"], "") if p["env_key"] else ""
                result = _call_openai_compatible(p["base_url"], model or p["models"][0], messages, api_key)
                tried.append({"provider": p["id"], "status": "ok" if "error" not in result else "fail", "result": result})
                return {"provider": p["id"], "tried": tried, "result": result}
        return {"error": f"Unknown provider: {provider_id}", "tried": []}

    # Auto-failover across all configured providers
    for p in PROVIDERS:
        api_key = os.environ.get(p["env_key"], "") if p["env_key"] else ""
        # Skip if no key and not local ollama
        if not api_key and p["id"] not in ("ollama",):
            continue
        result = _call_openai_compatible(p["base_url"], model or p["models"][0], messages, api_key)
        tried.append({"provider": p["id"], "status": "ok" if "error" not in result else "fail"})
        if "error" not in result:
            return {"provider": p["id"], "tried": tried, "result": result}

    return {"error": "All providers failed or no keys configured", "tried": tried}
