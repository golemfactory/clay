from sha3 import sha3_256
import math
from ethereum.abi import encode_abi


def make_payment_list(payments):
    """ Change list of pairs describing payments into a payment list with tuples that can be put in lottery description
     tree leaves.
    :param list payments: containing pairs (address, value)
    :return payment list, lottery description triple (a, R, r). a will win lottery if a random value x is such that
        R <= x < r.
    """
    payment_list = []
    cnt = 0
    for (address, value) in payments:
        payment_list.append((address, cnt, cnt + value))
        cnt = cnt + value
    return payment_list


class MerkleTree(object):
    """ Merkle Tree structure that can help generating data for Ethereum lottery contract """
    def __init__(self, value):
        """ Create new leaf
        :param value: value stored in this node
        """
        self.value = value
        self.left = None
        self.right = None

    def __str__(self):
        return "(VALUE: {}, LEFT: {}, RIGHT: {})".format(self.value.encode('hex'), self.left, self.right)

    def produce_path(self, val):
        """ Produce a path from a leaf with given value to a root. For details check golem micropayment whitepaper
        :param val: start path from node that store given value
        :return (bool, list, list): (is node with given value in a tree?; list describing how to get to the node
            with given value: 0 - choose left path, 1 choose right path; list containing hashes of other children
            of a nodes on the path).
        """
        if self.value == val:
            return True, [], []
        if self.left:
            left_found, left_b, left_w = self.left.produce_path(val)
        else:
            left_found, left_b, left_w = False, [], []
        if self.right:
            right_found, right_b, right_w = self.right.produce_path(val)
        else:
            right_found, right_b, right_w = False, [], []
        if left_found:
            return True, left_b + [0], left_w + right_w
        if right_found:
            return True, right_b + [1], right_w + left_w

        return False, [], [self.value]

    def verify_path(self, path, values, leaf):
        """ Check that a tree contains given leaf. Leaf, path and values create together leaf certificate that can
        be send to verify that a leaf is in a tree with given value. Check Golem whitepaper for details.
        :param list path:  list describing how to get to the node  with given value: 0 - choose left path, 1 choose
            right path
        :param list values:   list containing hashes of other children of a nodes on the path
        :param leaf: value stored in a leaf
        :return bool: True if given leaf is in a tree and given proof is sufficient, False otherwise.
        """
        h = leaf
        for it in range(len(path)):
            if path[it] == 0:
                h = sha3_256(h + values[it]).digest()
            else:
                h = sha3_256(values[it] + h).digest()
        return h == self.value

    @classmethod
    def make_tree(cls, payment_list):
        """ Generate new Merkle Tree form given payment list
        :param list payment_list: list containing lottery description triples (a, R, r).
            a will win lottery if a random value x is such that R <= x < r.
        :return MerkleTree: root of a created merkle tree describing lottery
        """
        nodes = cls.generate_leaves(payment_list)
        for t in nodes:
            print t
        n = len(nodes)
        lvl = int(math.log(n, 2))
        lvl_pairs = n - 2 ** lvl
        nodes = cls.__generate_next_layer(nodes[:lvl_pairs * 2]) + nodes[lvl_pairs * 2:]
        while len(nodes) > 1:
            for t in nodes:
                print t
            nodes = cls.__generate_next_layer(nodes)
        return nodes

    @classmethod
    def generate_leaves(cls, payment_list):
        """ Generate leaves of merkle tree from given payment list
        :param list payment_list: list containing lottery description triples (a, R, r)
        :return list: list of a hashed values, each representing one address. Each value should be stored in one merkle
        tree leaf.
        """
        hash_list = []
        for (address, R, r) in payment_list:
            data = encode_abi(['uint256'], [address]) + encode_abi(['uint256'], [R]) + encode_abi(['uint256'], [r])
            data = encode_abi(['bytes32'], [sha3_256(data).digest()])
            hash_list.append(MerkleTree(data))
        return hash_list

    @classmethod
    def __generate_next_layer(cls, nodes):
        new_nodes = []
        n = len(nodes)
        for i in range(0, n, 2):
            if i + 1 < n:
                t = MerkleTree(sha3_256(nodes[i].value + nodes[i + 1].value).digest())
                t.left = nodes[i]
                t.right = nodes[i + 1]
                nodes[i].parent = t
                nodes[i].parent = t
                new_nodes.append(t)
            else:
                new_nodes.append(MerkleTree(nodes[i].value))
        return new_nodes


if __name__ == "__main__":

    l = [('45b4ab30803739e31925387c2f354bcb8a1c7d66', 2), ('745ae7f60baf85e58f0920521e1e292e981ee7da', 3),
         ('c739c289657385076e0bc3c1bc06079e4624569a', 4)]
    pl = make_payment_list(l)
    print pl
    cr = MerkleTree.make_tree(pl)
    root = cr[0]
    print "ROOT BEFORE {}".format(encode_abi(['bytes32'], [sha3_256(root.value + '123').digest()]).encode('hex'))
    print "ROOT"
    print root
    addr, path, value = root.produce_path(root.generate_leaves([('745ae7f60baf85e58f0920521e1e292e981ee7da', 2, 5)])[0].value)
    print path
    print value

    l = [('r1', 2), ('r2', 3), ('r3', 1), ('r4', 2), ('r5', 6), ('r6', 6), ('r7', 8), ('r8', 8)]
    pl = make_payment_list(l)
    print pl
    cr = MerkleTree.make_tree(pl)
    print "ROOT"
    root = cr[0]
    print root
    print "PATH"
    leaf = root.generate_leaves([('r3', 5, 6)])[0].value
    _, path, value = root.produce_path(root.generate_leaves([('r3', 5, 6)])[0].value)
    for i in value:
        print i.encode('hex')
    print root.verify_path(path, value, leaf)