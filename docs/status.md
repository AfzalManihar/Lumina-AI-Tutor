# Status matrix

Updated with the final verification run (see README for commands).

**Implemented and tested (mock providers, fake MongoDB):** authentication and sessions, authorization and isolation, documents and RAG pipeline, supervisor workflow with router/planner/verifier, tool registry, guardrails, memory, lessons, quizzes, progress, usage metering, Razorpay billing logic, evaluation harness, index-readiness guard.

**Implemented, not live-tested:** Groq client (`openai/gpt-oss-120b`), Google embeddings client, Razorpay Orders API client and browser checkout, behaviour on a real MongoDB or Atlas, frontend pages in a real browser against the real API, PowerShell scripts.

**Partially implemented:** Langfuse (status and host reachability only; no trace delivery). Vector search (MongoDB-stored vectors with in-process cosine only).

**Not implemented:** Pinecone, web search, email/OTP, password reset, MFA, streaming responses, account export/deletion, distributed rate limiting.

## Scope guard (off-topic) - measured, with limits
- Pattern layer: labeled regression set (English + Hinglish) passes fully; this set was used to write the patterns.
- Held-out check before the final fixes: 25 unseen off-topic phrasings, 21 caught (84%); 25 unseen study questions, 1 wrongly refused (4%). Fixed afterwards.
- LLM layer (`off_topic` classifier verdict): exercised only with a scripted model. Its real-world accuracy is unknown.
- Not covered: other languages, indirect or disguised requests, long messages mixing study and non-study content.
