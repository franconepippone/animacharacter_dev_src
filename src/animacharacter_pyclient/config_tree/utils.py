from __future__ import annotations

def deep_merge(dst: dict, src: dict):
    for k, v in src.items():
        if (
            k in dst and
            isinstance(dst[k], dict) and
            isinstance(v, dict)
        ):
            deep_merge(dst[k], v)
        else:
            dst[k] = v

class ConfigNode:
    def __init__(self, name: str | None = None, parent: ConfigNode | None = None):
        self.name = name
        self.parent = parent
        self._children: dict[str, ConfigNode] = {}
        self._data: dict = {}

    # --- tree building ---

    def child(self, name: str) -> ConfigNode:
        if name not in self._children:
            self._children[name] = ConfigNode(name, self)
        return self._children[name]

    # --- publishing ---

    def publish(self, key: str, value: dict):
        """
        Publish config at this node.
        key = actuator id (string)
        value = config dict
        """
        if key not in self._data:
            self._data[key] = {}

        deep_merge(self._data[key], value)

    # --- build config ---

    def build(self) -> dict:
        result = {}

        # include local actuator configs
        for k, v in self._data.items():
            result[k] = v

        # include children recursively
        for name, child in self._children.items():
            child_data = child.build()
            if child_data:
                result[name] = child_data

        return result

    # --- root helpers ---

    def root(self) -> ConfigNode:
        if self.parent is None:
            return self
        else:
            return self.parent.root()
    
    def get_config(self) -> dict:
        return self.root().build()

    def clear(self):
        self._data.clear()
        for child in self._children.values():
            child.clear()



if __name__ == "__main__":
    root = ConfigNode('')
    ch1 = root.child('chi1')
    ch2 = root.child('chi2')
    ch1_1 = ch1.child('bob')
    ch2_1 = ch1.child('bill')
    ch1_2 = ch2.child('pino').child('di').child('pina')

    ch1.publish('mytopic', {'ciro': [1,2,3]})
    ch1.publish('mytopic', {'bobby': 2})
    ch1.publish('mytopic', {'ciro': [5]})
    ch1_2.publish('hi', {})
    ch1_2.publish('hi', {'moby': 'dick'})
    ch2_1.publish('', {3:2})

    print(root.get_config())
