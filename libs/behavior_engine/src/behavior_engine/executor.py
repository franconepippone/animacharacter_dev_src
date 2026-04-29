import time
from typing import Generic, List
from collections.abc import Iterator
from .behavior import BehaviorInstance, BehaviorCallable, AbstractBehavior, ContextT
from .context import BehaviorContext


class BehaviorExecutor(Generic[ContextT]):
    """
    Core engine that schedules and executes behaviors.
    """

    def __init__(self, ctx: ContextT):
        """Create an executor using the shared behavior context."""
        self.ctx = ctx
        self.behaviors: List[BehaviorInstance] = []

    def add(self, behavior_fn: BehaviorCallable[ContextT], priority: int = 0) -> BehaviorInstance:
        """Start a behavior and return its runtime instance."""
        gen = behavior_fn(self.ctx)

        # Ensure it's a a valid object
        if not isinstance(gen, Iterator):
            raise TypeError("Behaviour fn must return an iterator")

        instance = BehaviorInstance(gen, priority)
        self.behaviors.append(instance)

        # keep execution order deterministic and based on priority
        self.behaviors.sort(key=lambda b: b.priority)
        return instance

    def remove(self, instance: BehaviorInstance) -> None:
        """Stop a running behavior instance."""
        if instance in self.behaviors:
            self.behaviors.remove(instance)

    def tick(self):
        """Advance all running behaviors by one time step."""
        time_now = time.monotonic()
        self.ctx.time._sync_time = time_now # all behavior have syncronized time for this iteration

        for b in tuple(self.behaviors):
            #print("ticking", b)
            action = b.step(time_now)

            if action is None:
                continue

            b.handle_action(action, time_now)
            # if marked as done, remove it
            if b.done: self.behaviors.remove(b)




if __name__ == "__main__":
    from .actions import BehaviorAction
    
    def bh1(ctx: BehaviorContext):
        pub = ctx.create_publisher("ciccio")
        print("created pub")
        while True:
            pub.publish("hello")
            pub.publish("there")
            print("published!", ctx.time.time())
            yield BehaviorAction.continue_()
    
    def bh2(ctx: BehaviorContext):
        sub = ctx.create_subscriber("ciccio")
        yield
        for _ in range(10):
            print("bh2", [msg for msg in sub.pull()])
            yield BehaviorAction.sleep(.1)

    class bh3(AbstractBehavior):
        def setup(self):
            self.sub = self.ctx.create_subscriber("ciccio")
        
        def tick(self):
            print("bh3", [msg for msg in self.sub.pull()])
    

    ctx = BehaviorContext()
    exec = BehaviorExecutor(ctx)
    exec.add(bh2, 0)
    exec.add(bh3, 0)
    exec.add(bh1, 0)

    print(exec.behaviors)
    exec.tick()
    while True:
        exec.tick()
        time.sleep(0.1)