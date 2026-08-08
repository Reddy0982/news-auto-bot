# World News Bot — Step 26: Human Review Mode

A controlled human-review layer now sits between the news queue and live X publishing.

## Decisions

Each story can be:
- `APPROVE`
- `REJECT`
- `HOLD`
- `PENDING` (default)

## Default safety

`X_REQUIRE_HUMAN_REVIEW=true`

Therefore, even if live X publishing is later enabled, an unapproved story is blocked.

## CLI review

After a dry run, a story can be reviewed with:

`python -m src.review_cli STORY_ID APPROVE`

or:

`python -m src.review_cli STORY_ID REJECT "reason"`

or:

`python -m src.review_cli STORY_ID HOLD "needs another source"`

The review is stored in `data/reviews.json`.

## Why this is useful

It allows the system to operate in three phases:

1. Dry run — observe everything.
2. Human review — approve selected stories.
3. Fully automatic mode — only after the system has demonstrated reliable behavior.

The default remains conservative.
