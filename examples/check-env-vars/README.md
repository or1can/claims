# Widget

Point `DATABASE_URL` at the database and set `STATION_NAME` to the
station's identifier. Responses are cached for `CACHE_TTL_SECONDS` seconds,
and retries are bounded by MAX_RETRIES. The server speaks plain `HTTP`
behind a `TLS` terminator.

```sh
export SECRET_KEY=change-me
```
