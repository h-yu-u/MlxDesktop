# ADR-003: SQLite metadata and local binary files

Status: Accepted

SQLite stores metadata and conversation text. Attachments and generated files live on disk. Runtime binds to loopback, requires an ephemeral desktop token, disables external compatibility APIs by default, and never enables remote model code by default.
