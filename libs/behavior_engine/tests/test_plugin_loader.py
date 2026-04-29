import tempfile
from pathlib import Path
from types import ModuleType

from behavior_engine import (
    AbstractBehavior,
    BehaviorAction,
    BehaviorContext,
    BehaviorEngine,
    behavior,
    discover_behaviors,
    load_behaviors_from_directory,
    load_behaviors_from_file,
    load_behaviors_from_module,
)


def test_behavior_decorator_registers_metadata():
    module = ModuleType("plugin_module")

    @behavior("hello", groups=["demo"], description="example")
    def hello(ctx: BehaviorContext):
        yield BehaviorAction.continue_()

    module.hello = hello

    discovered = discover_behaviors(module)
    assert len(discovered) == 1
    plugin = discovered[0]
    assert plugin.name == "hello"
    assert plugin.groups == ("demo",)
    assert plugin.metadata["description"] == "example"


def test_load_behaviors_from_module_registers_function_behavior():
    module = ModuleType("plugin_module")

    @behavior("hello", groups=["demo"])
    def hello(ctx: BehaviorContext):
        yield BehaviorAction.continue_()

    module.hello = hello
    engine = BehaviorEngine(BehaviorContext())
    load_behaviors_from_module(engine, module)

    entry = engine.get_behavior("hello")
    assert entry.name == "hello"

    instance = engine.play_behavior("hello")
    assert engine.is_running("hello")
    assert instance is not None
    engine.tick()
    engine.stop_all()
    assert engine.running_behaviors() == []


def test_load_behaviors_from_module_registers_class_behavior():
    module = ModuleType("plugin_module")

    @behavior("hello_class", groups=["demo"])
    class HelloBehavior(AbstractBehavior[BehaviorContext]):
        def setup(self):
            return BehaviorAction.continue_()

        def tick(self):
            return BehaviorAction.stop()

    module.HelloBehavior = HelloBehavior
    engine = BehaviorEngine(BehaviorContext())
    load_behaviors_from_module(engine, module)

    engine.play_behavior("hello_class")
    engine.tick()
    assert not engine.is_running("hello_class")


def test_load_behaviors_from_file_loads_module_behaviors():
    with tempfile.TemporaryDirectory() as tmpdir:
        plugin_path = Path(tmpdir) / "plugin_module.py"
        plugin_path.write_text(
            "from behavior_engine import behavior, BehaviorAction\n"
            "@behavior('file_behavior', groups=['file'])\n"
            "def file_behavior(ctx):\n"
            "    yield BehaviorAction.continue_()\n"
        )

        engine = BehaviorEngine(BehaviorContext())
        load_behaviors_from_file(engine, plugin_path)

        entry = engine.get_behavior("file_behavior")
        assert entry.name == "file_behavior"


def test_load_behaviors_from_directory_loads_all_py_files():
    with tempfile.TemporaryDirectory() as tmpdir:
        plugin_dir = Path(tmpdir)
        (plugin_dir / "plugin_a.py").write_text(
            "from behavior_engine import behavior, BehaviorAction\n"
            "@behavior('a', groups=['dir'])\n"
            "def a(ctx):\n"
            "    yield BehaviorAction.continue_()\n"
        )
        (plugin_dir / "plugin_b.py").write_text(
            "from behavior_engine import behavior, BehaviorAction\n"
            "@behavior('b', groups=['dir'])\n"
            "def b(ctx):\n"
            "    yield BehaviorAction.continue_()\n"
        )

        engine = BehaviorEngine(BehaviorContext())
        load_behaviors_from_directory(engine, plugin_dir)

        assert {entry.name for entry in engine.loaded_behaviors()} == {"a", "b"}
