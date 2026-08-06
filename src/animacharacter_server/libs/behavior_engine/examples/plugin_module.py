from behavior_engine import BehaviorAction, behavior


@behavior("say_hello", groups=["plugin", "example"], description="Print a greeting")
def say_hello(ctx):
    print("Hello from the plugin")
    yield BehaviorAction.stop()
