"""Layer 3 through the Message Batches API: one batch holds the narrative request of every course,
at half the price of synchronous calls. The request is the same one the sync path sends
(narrative.request_params); guards, the single retry and the fallback run afterwards, per course."""
import json
import sys
import time
from pathlib import Path

from . import narrative


def _client():
    import anthropic  # optional dependency
    return anthropic.Anthropic()


def submit(client, facts_by_id, model=None):
    """facts_by_id: {custom_id: facts}. custom_id must match ^[a-zA-Z0-9_-]{1,64}$. Returns the batch id."""
    from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
    from anthropic.types.messages.batch_create_params import Request
    reqs = [Request(custom_id=cid, params=MessageCreateParamsNonStreaming(**narrative.request_params(f, model=model)))
            for cid, f in facts_by_id.items()]
    return client.messages.batches.create(requests=reqs).id


def wait(client, batch_id, poll=30, log=print):
    while True:
        b = client.messages.batches.retrieve(batch_id)
        if b.processing_status == "ended":
            return b
        c = b.request_counts
        log(f"batch {batch_id}: {b.processing_status} · processing {c.processing}, succeeded {c.succeeded}, errored {c.errored}")
        time.sleep(poll)


def collect(client, batch_id):
    """{custom_id: (text, usage)} for succeeded requests, {custom_id: error string} for the rest.
    The caller holds the client: the results stream is read lazily, and a client that is garbage-collected
    mid-iteration closes the connection under it."""
    ok, failed = {}, {}
    for r in client.messages.batches.results(batch_id):
        res = r.result
        if res.type == "succeeded":
            try:
                ok[r.custom_id] = (narrative.reply_text(res.message), narrative.usage_of(res.message, batch=True))
            except RuntimeError as e:  # refusal or truncation
                failed[r.custom_id] = str(e)
        elif res.type == "errored":
            failed[r.custom_id] = f"errored: {res.error.type}"
        else:
            failed[r.custom_id] = res.type  # canceled / expired
    return ok, failed


def run(facts_by_id, out, model=None, batch_id=None, poll=30, log=lambda m: print(m, file=sys.stderr)):
    """Submit (or resume) a batch, wait for it and return ({custom_id: (text, usage)}, {custom_id: error}).
    The batch id is saved to out/llm_batch.json right after submission, so an interrupted run can resume."""
    state = Path(out) / "llm_batch.json"
    client = _client()
    if not batch_id:
        batch_id = submit(client, facts_by_id, model=model)
        state.write_text(json.dumps({"batch_id": batch_id, "custom_ids": sorted(facts_by_id)}, indent=1), encoding="utf-8")
        log(f"submitted batch {batch_id} with {len(facts_by_id)} requests (saved to {state}; resume with --batch-id)")
    wait(client, batch_id, poll=poll, log=log)
    return collect(client, batch_id)
