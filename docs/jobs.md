# Serving runbook

The document worker is in-process. Restarting the API replays nothing; jobs persist in the JSON store.
Re-submit with the same idempotency key to avoid duplicate work.
