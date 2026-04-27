import hashlib
import json
import threading
import time
from typing import Optional

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

app = FastAPI(title="Idempotency Gateway")

cache = {}
in_flight = {}
lock = threading.Lock()

TTL = 86400
CURRENCIES = {"RWF", "GHS"}


class PaymentRequest(BaseModel):
    amount: float = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3)

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v):
        v = v.upper()
        if v not in CURRENCIES:
            raise ValueError(f"Currency must be one of: {', '.join(sorted(CURRENCIES))}")
        return v


def hash_payment(payment):
    data = json.dumps({"amount": payment.amount, "currency": payment.currency}, sort_keys=True)
    return hashlib.sha256(data.encode()).hexdigest()


def purge_expired():
    cutoff = time.time() - TTL
    expired = [k for k, v in cache.items() if v["created_at"] < cutoff]
    for k in expired:
        cache.pop(k, None)
        in_flight.pop(k, None)


@app.post("/process-payment")
def process_payment(
    payment: PaymentRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
):
    if not idempotency_key:
        raise HTTPException(status_code=400, detail="Idempotency-Key header is required.")

    req_hash = hash_payment(payment)
    pending = None

    with lock:
        purge_expired()
        existing = cache.get(idempotency_key)

        if existing:
            if existing["status"] == "processing":
                pending = in_flight[idempotency_key]
            elif existing["body_hash"] != req_hash:
                raise HTTPException(status_code=422, detail="This key was already used with a different request body.")
            else:
                return JSONResponse(
                    content=existing["response"],
                    status_code=existing["status_code"],
                    headers={"X-Cache-Hit": "true"},
                )
        else:
            event = threading.Event()
            in_flight[idempotency_key] = event
            cache[idempotency_key] = {
                "body_hash": req_hash,
                "status": "processing",
                "response": None,
                "status_code": None,
                "created_at": time.time(),
            }

    if pending:
        pending.wait(timeout=30)
        with lock:
            existing = cache.get(idempotency_key)
        if existing and existing["status"] == "done":
            return JSONResponse(
                content=existing["response"],
                status_code=existing["status_code"],
                headers={"X-Cache-Hit": "true"},
            )
        raise HTTPException(status_code=503, detail="Timed out waiting for in-flight request.")

    try:
        time.sleep(2)

        response = {"status": "success", "message": f"Charged {payment.amount} {payment.currency}"}
        status_code = 201

        with lock:
            cache[idempotency_key]["status"] = "done"
            cache[idempotency_key]["response"] = response
            cache[idempotency_key]["status_code"] = status_code
            done_event = in_flight.pop(idempotency_key, None)

        if done_event:
            done_event.set()

        return JSONResponse(content=response, status_code=status_code)

    except Exception:
        with lock:
            cache.pop(idempotency_key, None)
            failed_event = in_flight.pop(idempotency_key, None)
        if failed_event:
            failed_event.set()
        raise
