from animacharacter_pyclient.animadummies.teodore import create_dummy
from animacharacter_pyclient.config_tree import ConfigNode

def actuator_configs(group: dict):
    for key, value in group.items():
        if isinstance(key, str):
            axis_name, idstr = key.split('@')
            axis_id = int(idstr)
            yield (axis_name, axis_id, value) 

teod = create_dummy()

print(teod.cfgpub, teod.head.eyebox.cfgpub)

teod.head.eyebox.eyelid_bl.set_exp_decay(0.5)
teod.head.eyebox.eyelid_bl.set_lower_limit(-1)
teod.head.eyebox.eyelid_bl.set_upper_limit(1)
teod.head.eyebox.eyes_h.configure({
    'closed': True,
    'gay': True,
    'mode': "mamta",
    'max_wideness': 120
    }
)

teod.arm_left.rotation.configure({'hello': 3})
teod.body.turn.set_max_velocity(100)
teod.body.turn.set_accel(50)
teod.arm_right.shoulder.motorA.configure({'exp_decay': 0.5})
teod.arm_right.shoulder.motorB.configure({'exp_decay': 0.5})
teod.head.ear_left.configure({'exp_decay': 0.5})
teod.head.mouth.configure({'vel_profile': 'TRAPEZOIDAL', 'accel': 20, 'max_vel' : 25})



cfg = teod.cfgpub.get_config()
print(cfg)


for id, name, value in actuator_configs(cfg['head']['eyes']):
    print(name, id, value)

import json

with open('tests/config.json', 'w') as f:
    json.dump(cfg, f, indent=3)
