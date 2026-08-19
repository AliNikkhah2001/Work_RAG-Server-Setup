# Redis Data Structures

Redis is an in-memory key-value store supporting strings, hashes, lists, sets, sorted sets,
bitmaps, hyperloglogs, and streams. Sorted sets (ZSET) use a skip list and a hash table,
giving O(log N) for ordered operations. Redis 7 added Redis Functions as a replacement for
EVAL scripts. Persistence options are RDB snapshots (point-in-time) and AOF (append-only file,
everysec default fsync policy). Max memory policy `allkeys-lru` evicts least-recently-used keys.
