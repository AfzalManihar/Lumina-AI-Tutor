# Security notes

Threats considered and what the code does about them. Nothing here has had an external security review.

| Threat | Mitigation | Limits |
|---|---|---|
| Credential stuffing / brute force | Argon2id hashes; login throttled per email+IP; safe, uniform error messages | Throttle state is in process memory (reset on restart, not shared across workers) |
| Token theft | 15-minute access JWT held only in memory; refresh token httpOnly, SameSite=Strict, stored hashed, rotated each use; replay revokes all sessions | XSS in the app could still use the in-memory token while the page is open |
| CSRF | SameSite=Strict cookie plus required `X-Requested-With` header on cookie-authenticated auth calls; bearer auth elsewhere | |
| Cross-user data access | Every query filters by the authenticated user id from the verified token/session; ObjectIds validated; role read from the database | Covered by tests for documents, memory, conversations, lessons, quizzes, billing |
| Prompt injection (chat) | Pattern flagging, system prompt separation, schema-validated outputs, tools allowlisted and permissioned, writes need approval | Regex heuristics miss paraphrase, obfuscation and other languages |
| Prompt injection (documents) | Retrieved text wrapped as untrusted data; model told not to follow it; memory writes need user click; tools cannot be chosen by document text | Not a guarantee. A model may still be influenced |
| Hallucinated citations | Citation ids validated against the retrieved set; passages shown come from stored chunks, not from the model | Lexical support check is heuristic |
| Upload abuse | Size cap, magic-byte type detection, page cap, encrypted/empty/corrupt rejection, text extracted only (nothing executed) | PDF parser vulnerabilities in dependencies are out of scope here |
| Payment fraud | Server-side price; HMAC signature verification for checkout and webhook (constant-time); amount match check; idempotent activation; unique order and event keys | Provider payloads written from documentation and mocked, not observed live |
| Quota bypass / races | Atomic reserve-then-settle in one conditional update | Verified on a fake MongoDB only |
| Secret leakage | Secrets only server-side; redaction in traces and model output; admin diagnostics show configured/not configured | |
| Writes before indexes exist | 503 on all writes until unique indexes are created | |
