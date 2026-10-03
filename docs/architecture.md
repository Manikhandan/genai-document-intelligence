# Architecture

JobStore is the source of truth. The Processor is a function over a job id.
The API authenticates, enqueues, and can drain. Review is a first-class state,
not a log line.
