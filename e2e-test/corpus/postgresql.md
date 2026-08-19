# PostgreSQL Performance Tuning

PostgreSQL uses a multi-version concurrency control (MVCC) model. The `shared_buffers` parameter
defaults to 128 MB and is typically set to 25% of total RAM. WAL (Write-Ahead Log) files are stored
in the `pg_wal` directory, and increasing `checkpoint_timeout` reduces disk write frequency.
PostgreSQL 16 introduced `pg_stat_io` for detailed I/O statistics. Autovacuum runs automatically
every 1 minute by default (autovacuum_naptime) to reclaim dead tuples.
