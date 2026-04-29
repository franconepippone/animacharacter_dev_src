# behaviour_plugin.py
#from animacharacter.behaviours import (
#  behaviour,
#  TimeUtil,
#  BehaviourAction
#)
#from animacharacter.behaviours import BehaviourInterface as Interface
from behavior_engine import BehaviorContext, BehaviorAction
from typing import Generator, Literal

def behaviour(name, group=None, every_ms=0):
    def dec(f):
        pass
    return dec

class VirtualAxis:
    def __init__(self, id) -> None:
        self.id = id
        self.value = 0
    def changed(self) -> bool:
       return False

class BooleanAxis(VirtualAxis):
    def is_true(self) -> bool: return True

class ConfigSubscription:
   def has_new(self) -> bool: ...
   def data(self) -> dict: ...

class EngineInterface(BehaviorContext):
    def publish_motion_cmd(self, id, value): ...
    def publish_config(self, dict): ...
    def subscribe_to_conifg(self, path) -> ConfigSubscription: ...

    # interacting with other behaviours
    def play_behaviour(self, name, loop = False): ...
    def stop_behaviour(self, name, loop = False): ...
    def get_loaded_behaviours(self): ...
    def get_running_behaviours(self): ...

    # these all use floats under the hood
    def create_virtual_axis(self, id, override: bool = True) -> VirtualAxis:
       return VirtualAxis(id)
    def create_boolean_axis(self, id, override: bool = True) -> BooleanAxis:
       return BooleanAxis(id)
    def create_integer_axis(self, id, range, override: bool = True) -> VirtualAxis: return VirtualAxis(id)
    
    # internally uses configurations to receive arbitrary data
    def create_data_channel(self, name: str): ...

    # low level
    def get_latest_axis_value(self, id): ...
    def get_latest_config(self): ...
    def acquire_axis_ids(self, ids): ... # stops hw mng from reacting to them
    def release_axis_ids(self): ... # realeases them
    def send_to_client(self, data): ...


def behaviour_action(action: Literal["continue", "stop", "sleep"], arg = 0):
   return (action, arg)

@behaviour(name="blink", group="idle_animations", every_ms=1000)
def blinking(intf: EngineInterface) -> Generator:
    BLINK_ID = 52
    while True:
    # every 1.5 seconds, send a blink cmd
        if intf.time.time() % 1500 == 0:
            pass
            # interface è l'interfaccia verso il meccanismo di
            # send/recv di motionframes su ros
        intf.publish_motion_cmd(BLINK_ID, 1.0)
        yield BehaviorAction.sleep(10)

# every_ms si può usare per specificare che il behaviour
# deve essere eseguito a almeno 10ms di distanza
@behaviour(name="neck_controller", every_ms=20)
def neck_control(intf: EngineInterface):
  """
  A behaviour for translating virtua roll/pitch
  neck motion into actual motor commands running as
  a differential pair
  """
  ROLL_VIRTUAL_AXIS = 16
  PITCH_VIRTUAL_AXIS = 17
  roll_axis = intf.create_virtual_axis(id=ROLL_VIRTUAL_AXIS, override=True)
  pitch_axis = intf.create_virtual_axis(id=PITCH_VIRTUAL_AXIS)
  config = intf.subscribe_to_conifg(path='config/path')
  while True:
    if roll_axis.changed() or pitch_axis.changed():
      # if the value has changed since previous call
      roll, pitch = roll_axis.value, pitch_axis.value
      neck_l = 0#.. compute it ..
      neck_r = 0#.. compute it ..
      intf.publish_motion_cmd(NECK_L_ID, neck_l)
      intf.publish_motion_cmd(NECK_R_ID, neck_r)
    yield BehaviorAction.continue_()

    intf.publish_config({}) # any dict

    # potenzialmente intf puo esporre anche metodi a piu basso livello
    # come: (che è internamente chiamato dagli oggetti "virtual_axis")
    #intf.get_latest_value(from_axis_id: int) -> float | None (o 0)
    # per convenienza, si possono creare anche assi booleane
    # (internamente utilizzano sempre i float)
    flag = intf.create_boolean_axis(ID)
    flag.is_true() # True / False
    flag.changed()
    #Se non si vuole creare un generatore, viene offerta anche una classe da cui ereditare:



#from animacharacter.behaviour Behaviour
# the behaviour class acts exactly as a
# generator with a while loop.
# the tick method is called repeatedly inside that loop.
@behaviour(name="test")
class MyBehaviour(Behaviour):
  def __init__(self):
    #... custom code...
  def tick(self, time: TimeUtil, intf: Interface):
    #... custom code...






