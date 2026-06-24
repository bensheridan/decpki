import hashlib

from decpki.merkle import build_tree, get_proof, get_root, verify_proof, _leaf_hash


def _node_hash(left, right):
    return hashlib.sha256(b"\x01" + left + right).digest()


def test_single_leaf_tree():
    data = b"hello"
    tree = build_tree([data])
    root = get_root(tree)
    assert root == _leaf_hash(data)
    proof = get_proof(tree, 0)
    assert verify_proof(data, proof, root)


def test_two_leaf_tree():
    leaves = [b"a", b"b"]
    tree = build_tree(leaves)
    root = get_root(tree)
    expected = _node_hash(_leaf_hash(b"a"), _leaf_hash(b"b"))
    assert root == expected
    assert verify_proof(b"a", get_proof(tree, 0), root)
    assert verify_proof(b"b", get_proof(tree, 1), root)


def test_four_leaf_tree():
    leaves = [b"a", b"b", b"c", b"d"]
    tree = build_tree(leaves)
    root = get_root(tree)
    for i, leaf in enumerate(leaves):
        assert verify_proof(leaf, get_proof(tree, i), root)


def test_odd_leaf_count_duplicates_last():
    leaves = [b"a", b"b", b"c"]
    tree = build_tree(leaves)
    root = get_root(tree)
    # last leaf is duplicated: tree[0] = [h(a), h(b), h(c), h(c)]
    ab = _node_hash(_leaf_hash(b"a"), _leaf_hash(b"b"))
    cc = _node_hash(_leaf_hash(b"c"), _leaf_hash(b"c"))
    expected = _node_hash(ab, cc)
    assert root == expected
    for i, leaf in enumerate(leaves):
        assert verify_proof(leaf, get_proof(tree, i), root)


def test_wrong_leaf_fails_proof():
    leaves = [b"a", b"b"]
    tree = build_tree(leaves)
    root = get_root(tree)
    assert not verify_proof(b"z", get_proof(tree, 0), root)
