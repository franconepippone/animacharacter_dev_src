from __future__ import annotations
import json

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

class Node:
    """
    Represents a node in a hierarchical json-based tree.

    Each node exists under a unique name (or "topic") and can have child nodes,
    forming a tree structure. Each node can publish data as JSON serializable
    values to specific keys.

    Calling `gather()` returns the complete rendered tree (from that node downards) as
    a nested json serializable dictionary. Each publication is put at the corresponding dictionary path defined by the 
    node position inside the node tree hierarchy. All publications can be cleared by calling `clear()`.
    """

    def __init__(self, name: str = '', parent: Node | None = None):
        self.name = name
        self.parent = parent
        if parent is not None:
            parent.add_child(self)
        self._children: dict[str, Node] = {}
        self._data: dict = {}

    # --- tree building ---

    def add_child(self, node: Node):
        """
        Adds a child node to this node
        """
        if node.name not in self._children:
            self._children[node.name] = node

    def child(self, name: str) -> Node:
        return Node(name, self)

    # --- publishing ---

    def publish(self, key: str, value: dict):
        """
        Publish json data at this node under a specified key.
        `value` must be a JSON-serializable object.
        """
        if key not in self._data:
            self._data[key] = {}

        deep_merge(self._data[key], value)

    # --- build rendered tree ---

    def _build(self) -> dict:
        result = {}

        for k, v in self._data.items():
            result[k] = v

        # include children recursively
        for name, child in self._children.items():
            child_data = child._build()
            if child_data:
                result[name] = child_data

        return result

    # --- root helpers ---

    def get_root(self) -> Node:
        """
        Returns the root node of the current tree.
        """
        if self.parent is None:
            return self
        else:
            return self.parent.get_root()
    
    def gather(self) -> dict:
        """
        Builds and returns the complete configuration tree with all
        data published so far, considering this node as root.

        To get the full tree, call `get_root().gather()` instead.
        """
        return self._build()

    def clear(self):
        """
        Clears all publications from this tree,
        considering this node as the root.

        To clear the full tree, call `get_root().clear()`.
        """
        self._data.clear()
        for child in self._children.values():
            child.clear()
    
    def get_json(self) -> str:
        """
        Returns the json serialized result of `gather()`.

        To get json for the full tree, call `get_root().get_json()`.
        """
        return json.dumps(self.gather())

    def __repr__(self) -> str:
        return f"Node({self.name}, parent={self.parent})"

if __name__ == "__main__":
    root = Node('')
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

    print(root.gather())
