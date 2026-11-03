"""OpenRouter-compatible logging proxy for MAS and ChatDev."""

import json
import os
import time

import httpx
from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse

from mas.core.llm import (
    ModelResult,
    TokenCapExceededError,
    calculate_model_cost,
    estimate_prompt_tokens,
    is_model_match,
    resolve_openrouter_model,
    token_logger,
)

proxy_app = FastAPI(title="MAS Logging Proxy")

OPENROUTER_UPSTREAM_URL = os.environ.get(
    "OPENROUTER_UPSTREAM_URL",
    os.environ.get("OPENAI_UPSTREAM_URL", "https://openrouter.ai/api/v1"),
)


@proxy_app.get("/health")
def health():
    return {"status": "ok"}


@proxy_app.post("/v1/chat/completions")
async def chat_completions(request: Request, authorization: str = Header(None)):
    body = await request.json()
    raw_model = body.get("model", "openrouter/free")
    model = resolve_openrouter_model(raw_model)
    body["model"] = model
    # Strictly disable fallbacks for research integrity
    body["provider"] = {
        "allow_fallbacks": False,
    }
    # Suppress reasoning token consumption for reasoning and cohere models
    reasoning_limit_env = os.environ.get("OPENROUTER_REASONING_MAX_TOKENS")
    if reasoning_limit_env is not None:
        try:
            body["reasoning"] = {"max_tokens": int(reasoning_limit_env)}
        except ValueError:
            pass
    elif "reasoning" in model.lower() or "cohere" in model.lower():
        body["reasoning"] = {"max_tokens": 0}

    if "max_tokens" in body:
        body["max_tokens"] = min(int(body["max_tokens"]), 4000)
    else:
        body["max_tokens"] = 4000

    run_id = request.headers.get("X-Run-ID", "global-run")
    agent_name = request.headers.get("X-Agent-Name", "chatdev_or_external")

    t0 = time.time()

    reservation_id = None
    if run_id and run_id != "global-run":
        messages = body.get("messages", [])
        estimated_input = estimate_prompt_tokens(messages)
        requested_output = int(body.get("max_tokens", 2000))
        try:
            reservation_id, effective_max_tokens = token_logger.reserve_budget(
                run_id=run_id,
                estimated_input=estimated_input,
                requested_output=requested_output,
                min_safe_completion=50,
            )
            body["max_tokens"] = effective_max_tokens
        except TokenCapExceededError as e:
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "message": str(e),
                        "code": "TOKEN_CAP_EXCEEDED",
                    }
                },
            )

    # Forward to OpenRouter upstream if real API key is provided and not fake/mock
    api_key = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if authorization and authorization.startswith("Bearer "):
        api_key = authorization.split("Bearer ")[1].strip()

    if api_key and api_key != "dummy-key" and not api_key.startswith("mock") and not api_key.startswith("sk-1234"):
        stage_budget_str = os.environ.get("MAS_STAGE_MAX_SPEND")
        if stage_budget_str:
            try:
                stage_budget = float(stage_budget_str)
                current_spend = token_logger.get_stage_spend()
                conservative_call_cost = 0.035
                if current_spend + conservative_call_cost > stage_budget:
                    token_logger.release_reservation(reservation_id)
                    return JSONResponse(
                        status_code=402,
                        content={
                            "error": {
                                "message": f"Stage budget cap reached: current spend (${current_spend:.4f}) + projected call cost (${conservative_call_cost:.4f}) exceeds authorized limit of ${stage_budget:.2f}.",
                                "code": "BUDGET_CAP_EXCEEDED",
                            }
                        },
                    )
            except ValueError:
                pass

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/mas-team/mas",
            "X-Title": "MAS Multi-Agent Software Engineering Team",
        }
        try:
            from mas.core.governor import GovernedHTTPClient, DailyTransmissionsCeilingExceededError
            with GovernedHTTPClient(
                timeout=90.0,
                request_type="LIVE_GENERATION",
                target=model,
                source=f"{run_id}:{agent_name}",
            ) as client:
                resp = client.post(
                    f"{OPENROUTER_UPSTREAM_URL.rstrip('/')}/chat/completions",
                    json=body,
                    headers=headers,
                )
            latency = int((time.time() - t0) * 1000)
            if resp.status_code != 200:
                token_logger.release_reservation(reservation_id)
                return JSONResponse(status_code=resp.status_code, content=resp.json())
            data = resp.json()
        except DailyTransmissionsCeilingExceededError as e:
            token_logger.release_reservation(reservation_id)
            return JSONResponse(
                status_code=429,
                content={"error": {"message": str(e), "code": "DAILY_TRANSMISSIONS_CEILING_EXCEEDED"}},
            )
        except httpx.ConnectError as e:
            token_logger.release_reservation(reservation_id)
            return JSONResponse(
                status_code=502,
                content={"error": {"message": f"Proxy failed to connect to OpenRouter upstream: {e}"}},
            )
        except httpx.TimeoutException:
            token_logger.release_reservation(reservation_id)
            return JSONResponse(
                status_code=504,
                content={"error": {"message": "OpenRouter upstream request timed out after 90s."}},
            )
        except Exception as e:
            token_logger.release_reservation(reservation_id)
            return JSONResponse(
                status_code=500,
                content={"error": {"message": f"Proxy upstream exception: {e}"}},
            )
    else:
        # Local mock proxy mode for testing without external calls
        latency = int((time.time() - t0) * 1000)
        messages = body.get("messages", [])
        in_tok = 100 + len(str(messages)) // 20
        out_tok = 80
        data = {
            "id": f"proxy-mock-{int(time.time()*1000)}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "system_fingerprint": f"{model}-proxy-mock",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": json.dumps({"status": "completed", "files": ["app.py"], "summary": "Proxy generated response"}),
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": in_tok,
                "completion_tokens": out_tok,
                "total_tokens": in_tok + out_tok,
            },
        }

    # Extract strictly provider-reported usage fields
    usage = data.get("usage", {})
    in_tok = usage.get("prompt_tokens", 0) if usage else 0
    out_tok = usage.get("completion_tokens", 0) if usage else 0
    tot_tok = usage.get("total_tokens", in_tok + out_tok) if usage else 0

    actual_model = data.get("model")
    cost = calculate_model_cost(actual_model, in_tok, out_tok)

    raw_meta = {
        "id": data.get("id"),
        "model": actual_model,
        "system_fingerprint": data.get("system_fingerprint"),
        "usage": usage,
    }

    # Check for strict model match
    if not actual_model or not is_model_match(model, actual_model):
        res = ModelResult(
            text=data.get("choices", [{}])[0].get("message", {}).get("content", ""),
            model_name=actual_model or "UNKNOWN",
            requested_model=model,
            provider_model_version=data.get("system_fingerprint", actual_model or "UNKNOWN"),
            input_tokens=in_tok,
            output_tokens=out_tok,
            total_tokens=tot_tok,
            latency_ms=latency,
            request_id=data.get("id", "req-proxy"),
            estimated_cost=cost,
            raw_metadata=raw_meta,
            execution_mode="LIVE_API" if (api_key and not api_key.startswith("mock") and not api_key.startswith("sk-1234")) else "SIMULATED",
            token_provenance="PROVIDER_REPORTED" if usage else "UNAVAILABLE",
        )
        try:
            token_logger.record_call(run_id=run_id, agent=agent_name, result=res, reservation_id=reservation_id)
        except TokenCapExceededError:
            pass
        return JSONResponse(
            status_code=502,
            content={
                "error": {
                    "message": f"Model mismatch error: Requested '{model}', but upstream returned '{actual_model}'. Fallbacks are disabled.",
                    "code": "MODEL_MISMATCH",
                    "requested_model": model,
                    "actual_model": actual_model,
                }
            },
        )

    choice_msg = data.get("choices", [{}])[0].get("message", {})
    text_content = choice_msg.get("content") or ""
    if not text_content and choice_msg.get("reasoning"):
        text_content = choice_msg.get("reasoning") or ""

    # Record matched model call
    res = ModelResult(
        text=text_content,
        model_name=actual_model,
        requested_model=model,
        provider_model_version=data.get("system_fingerprint", actual_model),
        input_tokens=in_tok,
        output_tokens=out_tok,
        total_tokens=tot_tok,
        latency_ms=latency,
        request_id=data.get("id", "req-proxy"),
        estimated_cost=cost,
        raw_metadata=raw_meta,
        execution_mode="LIVE_API" if (api_key and not api_key.startswith("mock") and not api_key.startswith("sk-1234")) else "SIMULATED",
        token_provenance="PROVIDER_REPORTED" if usage else "UNAVAILABLE",
    )

    try:
        token_logger.record_call(run_id=run_id, agent=agent_name, result=res, reservation_id=reservation_id)
    except TokenCapExceededError as e:
        return JSONResponse(
            status_code=429,
            content={
                "error": {
                    "message": str(e),
                    "code": "TOKEN_CAP_EXCEEDED",
                }
            },
        )

    return JSONResponse(status_code=200, content=data)


@proxy_app.get("/health")
def health():
    return {"status": "ok", "service": "mas-logging-proxy"}
