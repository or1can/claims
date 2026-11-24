# 0001. Read order

## Status

Accepted.

## Context

Nothing recorded which entries were read.

## Decision

`Cache` holds at most `capacity` entries. `get` of a key it holds makes
that entry the newest.

## Consequences

A key in use stays in the cache.
