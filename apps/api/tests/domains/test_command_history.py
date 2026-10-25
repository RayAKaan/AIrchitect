from datetime import datetime, timezone
from app.domains.commands.history import CommandHistoryEntry, history_summary


def entry(command_id, second):
    return CommandHistoryEntry(command_id, "MoveBuilding", "u", "p", "v", "base", "result", "reason", datetime.fromtimestamp(second, tz=timezone.utc), "committed")


def test_history_is_newest_first_and_non_mutating():
    older, newer = entry("old", 1), entry("new", 2)
    source = [older, newer]
    result = history_summary(source)
    assert [item["command_id"] for item in result["entries"]] == ["new", "old"]
    assert source == [older, newer]
