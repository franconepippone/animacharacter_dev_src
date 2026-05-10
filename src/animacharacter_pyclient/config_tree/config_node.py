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
    """
    Represents a node in a hierarchical configuration tree.

    Each node exists under a unique name (or "topic") and can have child nodes,
    forming a tree structure. A node can publish configuration data as dictionaries
    (JSON-like format) to specific keys.

    Calling `get_config()` returns the complete configuration tree (from that node downards) as
    a nested dictionary. Each publication is put at the corresponding dictionary path defined by the 
    node position inside the node tree hierarchy. All publications can be cleared by calling `clear()`.
    """

    def __init__(self, name: str = '', parent: ConfigNode | None = None):
        self.name = name
        self.parent = parent
        if parent is not None:
            parent.add_child(self)
        self._children: dict[str, ConfigNode] = {}
        self._data: dict = {}

    # --- tree building ---

    def add_child(self, node: ConfigNode):
        """
        Adds a child node to this node
        """
        if node.name not in self._children:
            self._children[node.name] = node

    def child(self, name: str) -> ConfigNode:
        return ConfigNode(name, self)

    # --- publishing ---

    def publish(self, key: str, value: dict):
        """
        Publish config at this node under a specified key.
        `value` must be a JSON-serializable object.
        """
        if key not in self._data:
            self._data[key] = {}

        deep_merge(self._data[key], value)

    # --- build config ---

    def _build(self) -> dict:
        result = {}

        # include local actuator configs
        for k, v in self._data.items():
            result[k] = v

        # include children recursively
        for name, child in self._children.items():
            child_data = child._build()
            if child_data:
                result[name] = child_data

        return result

    # --- root helpers ---

    def get_root(self) -> ConfigNode:
        """
        Returns the root node of the current tree.
        """
        if self.parent is None:
            return self
        else:
            return self.parent.get_root()
    
    def get_config(self) -> dict:
        """
        Builds and returns the complete configuration tree with all
        published configs so far, considering this node as root.

        To get the full tree, call `get_root().get_config()` instead.
        """
        return self._build()

    def clear(self):
        """
        Clears all published configs from this configuration tree,
        considering this node as the root.

        To clear the full tree, call `get_root().clear()`.
        """
        self._data.clear()
        for child in self._children.values():
            child.clear()

    def __repr__(self) -> str:
        return f"ConfigNode({self.name}, parent={self.parent})"

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
