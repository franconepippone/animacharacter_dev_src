from pathlib import Path

from behavior_engine import BehaviorContext, BehaviorEngine, load_behaviors_from_file


def main() -> None:
    engine = BehaviorEngine(BehaviorContext())
    plugin_path = Path(__file__).with_name("plugin_module.py")

    load_behaviors_from_file(engine, plugin_path)
    engine.play_behavior("say_hello")

    while engine.running_behaviors():
        engine.tick()


if __name__ == "__main__":
    main()
