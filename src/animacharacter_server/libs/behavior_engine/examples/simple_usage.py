from behavior_engine import BehaviorAction, BehaviorContext, BehaviorEngine, AbstractBehavior


class RobotContext(BehaviorContext):
    def __init__(self):
        self.state = "idle"
        self.counter = 0


def blink_led(ctx: RobotContext):
    while ctx.counter < 3:
        print(f"Blink {ctx.counter + 1}")
        ctx.counter += 1
        yield BehaviorAction.sleep(0.5)
    yield BehaviorAction.stop()


class SayHelloBehavior(AbstractBehavior[RobotContext]):
    def setup(self):
        print("SayHelloBehavior setup")
        return BehaviorAction.continue_()

    def tick(self):
        print("Hello from behavior engine")
        self.ctx.state = "running"
        return BehaviorAction.stop()


def main():
    ctx = RobotContext()
    engine = BehaviorEngine(ctx)

    engine.load_behavior("blink", blink_led, groups=["led", "demo"])
    engine.load_behavior("hello", SayHelloBehavior)

    engine.play_behavior("blink")
    engine.play_behavior("hello")

    while engine.running_behaviors():
        engine.tick()

    print("Finished", ctx.state)


if __name__ == "__main__":
    main()
