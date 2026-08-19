# Web Security Fundamentals

OWASP Top 10 2021 ranks Broken Access Control first. SQL injection is prevented with parameterized
queries. XSS attacks inject client-side scripts; Content-Security-Policy headers mitigate them.
CSRF tokens protect state-changing requests. TLS 1.3 reduces handshake round trips to one.
Authentication should use bcrypt/argon2 with a per-user salt. Session cookies need the HttpOnly,
Secure, and SameSite attributes. Rate limiting (e.g., token bucket) defends against credential
stuffing.
