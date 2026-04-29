from behavior_engine import BehaviorAction, BehaviorContext, BehaviorEngine


def test_behavior_engine_load_and_play():
    engine = BehaviorEngine(BehaviorContext())

    def simple_behavior(ctx: BehaviorContext):
        yield BehaviorAction.continue_()

    engine.load_behavior("test", simple_behavior, groups=["group1"], description="simple")

    assert engine.get_behavior("test").name == "test"
    assert engine.get_behaviors_by_group("group1")[0].name == "test"
    assert engine.loaded_behaviors()[0].metadata["description"] == "simple"

    instance = engine.play_behavior("test")
    assert engine.is_running("test")
    assert engine.running_behaviors() == ["test"]
    assert instance is not None

    engine.tick()
    engine.stop_behavior("test")
    assert not engine.is_running("test")


def test_play_behavior_group_stops_all():
    engine = BehaviorEngine(BehaviorContext())

    def behavior_a(ctx: BehaviorContext):
        yield BehaviorAction.continue_()

    def behavior_b(ctx: BehaviorContext):
        yield BehaviorAction.continue_()

    engine.load_behavior("a", behavior_a, groups=["group2"])
    engine.load_behavior("b", behavior_b, groups=["group2"])

    engine.play_behavior_group("group2")
    assert set(engine.running_behaviors()) == {"a", "b"}

    engine.stop_all()
    assert engine.running_behaviors() == []


test_behavior_engine_load_and_play()
test_play_behavior_group_stops_all()