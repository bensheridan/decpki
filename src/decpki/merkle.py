import hashlib


def _leaf_hash(data: bytes) -> bytes:
    return hashlib.sha256(b"\x00" + data).digest()


def _node_hash(left: bytes, right: bytes) -> bytes:
    return hashlib.sha256(b"\x01" + left + right).digest()


def build_tree(leaves: list[bytes]) -> list[list[bytes]]:
    if not leaves:
        return [[hashlib.sha256(b"").digest()]]
    layer = [_leaf_hash(leaf) for leaf in leaves]
    tree = [layer]
    while len(layer) > 1:
        if len(layer) % 2 == 1:
            layer = layer + [layer[-1]]
        layer = [_node_hash(layer[i], layer[i + 1]) for i in range(0, len(layer), 2)]
        tree.append(layer)
    return tree


def get_root(tree: list[list[bytes]]) -> bytes:
    return tree[-1][0]


def get_proof(tree: list[list[bytes]], index: int) -> list[dict]:
    proof = []
    for layer in tree[:-1]:
        if len(layer) % 2 == 1:
            layer = layer + [layer[-1]]
        if index % 2 == 0:
            sibling = layer[index + 1] if index + 1 < len(layer) else layer[index]
            proof.append({"h": sibling, "s": "right"})
        else:
            proof.append({"h": layer[index - 1], "s": "left"})
        index //= 2
    return proof


def verify_proof(leaf_data: bytes, proof: list[dict], root: bytes) -> bool:
    current = _leaf_hash(leaf_data)
    for step in proof:
        sibling = step["h"]
        if step["s"] == "left":
            current = _node_hash(sibling, current)
        else:
            current = _node_hash(current, sibling)
    return current == root
