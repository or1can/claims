# Holds

A hold keeps stock back for one customer.

## Order of holds

`next_hold` returns the hold with the highest priority. Among holds of
equal priority, it returns the one placed first.

## Placing a hold

The customer's name is stored with the hold.
