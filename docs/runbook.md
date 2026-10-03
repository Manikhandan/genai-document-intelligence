# Document jobs

Jobs are durable in a JSON store. A retryable failure goes back on the queue with backoff.
Exhausted attempts land in the dead-letter list. Operators inspect `/v1/jobs/{id}` and `/v1/dead-letter`.
