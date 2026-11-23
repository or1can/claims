# 0001. The cache

## Status

Accepted.

## Context

`cache.py` had no limit, and grew without bound.

## Decision

`Cache` holds at most `capacity` entries. When it is full, `put` of a
new key evicts the oldest entry first.

## Consequences

A long run uses bounded memory.
