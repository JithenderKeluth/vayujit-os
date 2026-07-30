# ADR 0028: Campaign pause and missed-activity behavior

Pause affects future local schedules and unclaimed jobs, not remote operations already running.
Resume always requires an explicit missed-activity policy and never replays every missed activity
automatically.
