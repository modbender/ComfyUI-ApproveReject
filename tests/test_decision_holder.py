import asyncio

import pytest

from src.decision_holder import DecisionHolder


async def test_open_submit_wait_returns_decision_payload():
    holder = DecisionHolder()
    await holder.open("node-1")

    async def submitter():
        await asyncio.sleep(0.01)
        await holder.submit("node-1", {"action": "approve", "override_seed": None})

    submit_task = asyncio.create_task(submitter())
    decision = await holder.wait("node-1", timeout_s=1.0)
    await submit_task

    assert decision == {"action": "approve", "override_seed": None}


async def test_wait_returns_timeout_action_when_no_decision_arrives():
    holder = DecisionHolder()
    await holder.open("node-1")

    decision = await holder.wait("node-1", timeout_s=0.05)

    assert decision == {"action": "timeout"}


async def test_cancel_helper_submits_cancel_action():
    holder = DecisionHolder()
    await holder.open("node-1")

    async def canceller():
        await asyncio.sleep(0.01)
        await holder.cancel("node-1")

    cancel_task = asyncio.create_task(canceller())
    decision = await holder.wait("node-1", timeout_s=1.0)
    await cancel_task

    assert decision == {"action": "cancel"}


async def test_concurrent_gates_with_different_node_ids_do_not_cross_trigger():
    holder = DecisionHolder()
    await holder.open("node-A")
    await holder.open("node-B")

    async def submit_to_A():
        await asyncio.sleep(0.01)
        await holder.submit("node-A", {"action": "approve"})

    asyncio.create_task(submit_to_A())

    decision_A = await holder.wait("node-A", timeout_s=1.0)
    # B should still be open and time out cleanly
    decision_B = await holder.wait("node-B", timeout_s=0.05)

    assert decision_A == {"action": "approve"}
    assert decision_B == {"action": "timeout"}


async def test_submit_before_wait_is_seen_by_wait():
    holder = DecisionHolder()
    await holder.open("node-1")
    # Submit synchronously before any wait coroutine starts
    await holder.submit("node-1", {"action": "reject", "override_seed": 42})

    decision = await holder.wait("node-1", timeout_s=0.5)

    assert decision == {"action": "reject", "override_seed": 42}


async def test_wait_without_open_raises_key_error():
    holder = DecisionHolder()

    with pytest.raises(KeyError):
        await holder.wait("never-opened", timeout_s=0.05)


async def test_submit_to_unopened_node_returns_false():
    holder = DecisionHolder()

    submitted = await holder.submit("never-opened", {"action": "approve"})

    assert submitted is False


async def test_wait_returns_cancel_when_interrupt_check_returns_true():
    holder = DecisionHolder()
    await holder.open("node-1")

    interrupt_state = {"flag": False}

    def interrupt_check():
        return interrupt_state["flag"]

    async def trip_interrupt():
        await asyncio.sleep(0.05)
        interrupt_state["flag"] = True

    asyncio.create_task(trip_interrupt())

    decision = await holder.wait(
        "node-1",
        timeout_s=2.0,
        interrupt_check_fn=interrupt_check,
        poll_interval_s=0.01,
    )

    assert decision == {"action": "cancel"}


async def test_wait_cleans_up_state_after_decision():
    holder = DecisionHolder()
    await holder.open("node-1")
    await holder.submit("node-1", {"action": "approve"})
    await holder.wait("node-1", timeout_s=0.5)

    # After wait returns, a fresh wait without re-opening should KeyError
    with pytest.raises(KeyError):
        await holder.wait("node-1", timeout_s=0.05)
