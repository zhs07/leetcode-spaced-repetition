# Supabase database CA

`supabase-prod-ca-2021.crt` is a public CA certificate, not a credential. It was
downloaded from the link in the project's Supabase Database Settings on October
3, 2026:

https://supabase-downloads.s3-ap-southeast-1.amazonaws.com/prod/ssl/prod-ca-2021.crt

SHA-256 fingerprint:
`80:70:25:AD:50:D4:ED:21:9D:2C:9C:7D:29:9C:00:4F:82:4E:B0:0C:F7:F6:5A:FE:F6:07:D0:7B:72:E6:CA:FA`

The certificate expires April 26, 2031. The runtime pool verifies both the CA
and hostname by default. If Supabase rotates the root, download the replacement
from the official dashboard and verify a live connection before deploying it.
An explicit `sslrootcert` in the database URL can select another trusted CA file.

Reference: https://supabase.com/docs/guides/database/psql
