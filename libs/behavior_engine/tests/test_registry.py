from behavior_engine import BehaviorEntry, BehaviorRegistry


def test_register_and_lookup():
    registry = BehaviorRegistry()
    entry = registry.register(
        name="foo",
        behavior=lambda ctx: iter([]),
        groups=["alpha", "beta"],
        description="test behavior",
    )

    assert entry.name == "foo"
    assert entry.groups == ("alpha", "beta")
    assert registry.get("foo") is entry
    assert registry.by_group("alpha") == [entry]
    assert registry.by_group("beta") == [entry]
    assert registry.by_groups("alpha", "beta") == [entry]
    assert registry.all() == [entry]

def test_stress_registry():
    registry = BehaviorRegistry()
    for i in range(1000):
        registry.register(name=f"behavior_{i}", behavior=lambda ctx: iter([]), groups=[f"group_{i % 10}"])

    assert len(registry.all()) == 1000
    assert len(registry.by_group("group_0")) == 100
    assert len(registry.by_group("group_1")) == 100
    assert len(registry.by_group("group_9")) == 100

def test_borrow_and_release():
    registry = BehaviorRegistry()
    entry = registry.register("bar", behavior=lambda ctx: iter([]))

    assert not entry.borrowed

    borrowed_entry = registry.borrow("bar")
    assert borrowed_entry is entry
    assert entry.borrowed
    
    registry.release("bar")
    assert not entry.borrowed


test_register_and_lookup()
test_borrow_and_release()
test_stress_registry()