# 0001. Hold length

## Status

Accepted.

## Context

Holds were left open for days.

## Decision

A hold placed with no length lasts 15 minutes. `extend_hold` never takes a
hold past 60 minutes from when it was placed.

## Consequences

Customers collect sooner.
