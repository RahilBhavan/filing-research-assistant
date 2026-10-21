# Security

This project is a localhost research prototype. Do not expose its HTTP server
to a public network. Report security issues privately to the repository owner.

The server binds to `127.0.0.1`, checks the Host and Origin headers, applies a
restrictive Content Security Policy, never serves raw filing HTML, and avoids
logging questions or source text.

The Docker image binds to `0.0.0.0` inside the container. Set
`FILING_ALLOWED_HOSTS` to accept other Host names. `/api/answer` accepts at
most `FILING_ANSWERS_PER_MINUTE` requests per minute per process (default 30).
The Azure steps in `docs/DEPLOY-AZURE.md` have not been run.

Do not commit `.env` files, SEC contact
identities, credentials, or reviewer personal information.

