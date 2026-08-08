import json
import os
from datetime import datetime, timezone
from pathlib import Path

import requests


class XPublisherError(Exception):
    pass


class XPublisher:
    """
    Official X API v2 publisher.

    Live publishing is disabled unless:
        X_PUBLISH_ENABLED=true

    Production safety limits:
        - 40 successful original posts per UTC day
        - 3 successful posts in a rolling 30-minute window

    The publisher updates production_state.json only after
    successful X API responses.
    """

    DAILY_LIMIT = 40
    HALF_HOUR_LIMIT = 3

    def __init__(self):
        self.enabled = (
            os.getenv(
                "X_PUBLISH_ENABLED",
                "false"
            ).lower()
            == "true"
        )

        self.token = os.getenv(
            "X_USER_ACCESS_TOKEN",
            ""
        ).strip()

        self.base = (
            "https://api.x.com/2/tweets"
        )

        self.root = (
            Path(__file__)
            .resolve()
            .parents[1]
        )

        self.state_file = (
            self.root
            / "data"
            / "production_state.json"
        )

    # ---------------------------------------------------------
    # State
    # ---------------------------------------------------------

    def _load_state(self):
        if not self.state_file.exists():
            return {
                "live_enabled": False,
                "kill_switch": True,
                "daily_post_count": 0,
                "last_reset_date": None,
                "recent_post_times": [],
            }

        try:
            return json.loads(
                self.state_file.read_text()
            )
        except Exception as exc:
            raise XPublisherError(
                f"Unable to read production state: {exc}"
            )

    def _save_state(self, state):
        self.state_file.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        self.state_file.write_text(
            json.dumps(
                state,
                indent=2,
                ensure_ascii=False
            )
        )

    # ---------------------------------------------------------
    # State normalization
    # ---------------------------------------------------------

    def _prepare_state(self, state):
        now = datetime.now(
            timezone.utc
        )

        today = now.date().isoformat()

        # Automatic daily reset.
        if (
            state.get("last_reset_date")
            != today
        ):
            state["daily_post_count"] = 0
            state["last_reset_date"] = today
            state["recent_post_times"] = []

        # Keep only successful posts from
        # the last 30 minutes.
        recent = []

        for value in state.get(
            "recent_post_times",
            []
        ):
            try:
                timestamp = datetime.fromisoformat(
                    value.replace(
                        "Z",
                        "+00:00"
                    )
                )

                age = (
                    now - timestamp
                ).total_seconds()

                if 0 <= age < 1800:
                    recent.append(
                        timestamp.isoformat()
                    )

            except Exception:
                continue

        state["recent_post_times"] = recent

        return state

    # ---------------------------------------------------------
    # Safety gate
    # ---------------------------------------------------------

    def _check_allowed(self):
        if not self.enabled:
            return False

        state = self._prepare_state(
            self._load_state()
        )

        # Keep the state file synchronized even
        # when publishing is disabled.
        self._save_state(state)

        if state.get(
            "kill_switch",
            True
        ):
            raise XPublisherError(
                "Publishing blocked: kill switch is active"
            )

        if not state.get(
            "live_enabled",
            False
        ):
            raise XPublisherError(
                "Publishing blocked: production controller "
                "has not allowed live publishing"
            )

        daily_count = int(
            state.get(
                "daily_post_count",
                0
            )
        )

        if daily_count >= self.DAILY_LIMIT:
            raise XPublisherError(
                "Publishing blocked: daily limit reached"
            )

        half_hour_count = len(
            state.get(
                "recent_post_times",
                []
            )
        )

        if (
            half_hour_count
            >= self.HALF_HOUR_LIMIT
        ):
            raise XPublisherError(
                "Publishing blocked: 30-minute limit reached"
            )

        return True

    # ---------------------------------------------------------
    # HTTP
    # ---------------------------------------------------------

    def _headers(self):
        if not self.token:
            raise XPublisherError(
                "Missing X_USER_ACCESS_TOKEN"
            )

        return {
            "Authorization": (
                f"Bearer {self.token}"
            ),
            "Content-Type": (
                "application/json"
            ),
        }

    # ---------------------------------------------------------
    # Record successful post
    # ---------------------------------------------------------

    def _record_success(self):
        state = self._prepare_state(
            self._load_state()
        )

        now = datetime.now(
            timezone.utc
        )

        state["daily_post_count"] = (
            int(
                state.get(
                    "daily_post_count",
                    0
                )
            )
            + 1
        )

        state.setdefault(
            "recent_post_times",
            []
        ).append(
            now.isoformat()
        )

        self._save_state(state)

    # ---------------------------------------------------------
    # Create one X post
    # ---------------------------------------------------------

    def create_post(
        self,
        text,
        reply_to=None
    ):
        text = (text or "").strip()

        if not text:
            raise XPublisherError(
                "Cannot publish empty post"
            )

        # Dry-run mode.
        if not self.enabled:
            return {
                "mode": "dry_run",
                "text": text,
            }

        # Production safety gate.
        self._check_allowed()

        payload = {
            "text": text
        }

        if reply_to:
            payload["reply"] = {
                "in_reply_to_tweet_id": (
                    reply_to
                )
            }

        try:
            response = requests.post(
                self.base,
                headers=self._headers(),
                json=payload,
                timeout=20,
            )
        except requests.RequestException as exc:
            raise XPublisherError(
                f"X API request failed: {exc}"
            )

        # -----------------------------------------------------
        # Rate limiting
        # -----------------------------------------------------

        if response.status_code in (
            420,
            429,
        ):
            raise XPublisherError(
                "X API rate limit reached. "
                "Publishing stopped without retrying."
            )

        # -----------------------------------------------------
        # Other API errors
        # -----------------------------------------------------

        if response.status_code >= 300:
            raise XPublisherError(
                f"X API HTTP "
                f"{response.status_code}: "
                f"{response.text[:500]}"
            )

        try:
            result = response.json()
        except ValueError as exc:
            raise XPublisherError(
                f"Invalid X API response: {exc}"
            )

        # -----------------------------------------------------
        # Only NOW count the post.
        # -----------------------------------------------------

        self._record_success()

        return result

    # ---------------------------------------------------------
    # Publish story
    # ---------------------------------------------------------

    def publish(self, item):
        if not self.enabled:
            if item.get("format") == "single":
                return [
                    self.create_post(
                        item["post"]
                    )
                ]

            return [
                {
                    "mode": "dry_run",
                    "text": text,
                }
                for text in item.get(
                    "thread",
                    []
                )
            ]

        if item.get("format") == "single":
            return [
                self.create_post(
                    item["post"]
                )
            ]

        # -----------------------------------------------------
        # Thread
        # -----------------------------------------------------

        results = []
        previous = None

        for text in item.get(
            "thread",
            []
        ):
            result = self.create_post(
                text,
                previous
            )

            results.append(
                result
            )

            previous = (
                result.get("data") or {}
            ).get("id")

        return results
