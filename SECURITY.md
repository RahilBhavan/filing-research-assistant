# Security

This project is a localhost research prototype. Do not expose its HTTP server
to a public network. Report security issues privately to the repository owner.

The server binds to `127.0.0.1`, checks the Host and Origin headers, applies a
restrictive Content Security Policy, never serves raw filing HTML, and avoids
logging questions or source text. Do not commit `.env` files, SEC contact
identities, credentials, or reviewer personal information.

