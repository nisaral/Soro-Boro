from veyra.llm import chat_messages


def test_adjacent_user_turns_are_merged():
    merged = chat_messages([
        {"role": "system", "content": "rules"},
        {"role": "system", "content": "tools"},
        {"role": "user", "content": "task"},
        {"role": "user", "content": "state"},
    ])
    assert [m["role"] for m in merged] == ["system", "user"]
    assert "task" in merged[1]["content"] and "state" in merged[1]["content"]
