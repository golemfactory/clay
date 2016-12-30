class GossipKeeper(object):
    """ Keeps gossip and rankings that should be sent to other nodes or collected by Ranking """
    def __init__(self):
        """ Create new gossip keeper instance """
        self.gossip = []
        self.stop_gossip_from_peers = set()
        self.neighbour_loc_rank_buff = []

    def add_gossip(self, gossip):
        """ Add newly heard gossip to the gossip list
        :param list gossip: list of gossips from one peer
        """
        self.gossip.append(gossip)

    def pop_gossip(self):
        """ Return all gathered gossips and clear gossip buffer
        :return list: list of all gossips
        """
        gossip = self.gossip
        self.gossip = []
        return gossip

    def stop_gossip(self, id_):
        """ Register that peer with given id has stopped gossiping
        :param str id_: id of a string that has stopped gossiping
        """
        self.stop_gossip_from_peers.add(id_)

    def pop_stop_gossip_from_peers(self):
        """ Return set of all peers that has stopped gossiping
        :return set: set of peers id's
        """
        stop = self.stop_gossip_from_peers
        self.stop_gossip_from_peers = set()
        return stop

    def add_neighbour_loc_rank(self, neigh_id, about_id, rank):
        """
        Add local rank from neighbour to the collection
        :param str neigh_id: id of a neighbour - opinion giver
        :param str about_id: opinion is about a node with this id
        :param list rank: opinion that node <neigh_id> have about node <about_id>
        :return:
        """
        self.neighbour_loc_rank_buff.append([neigh_id, about_id, rank])

    def pop_neighbour_loc_ranks(self):
        """ Return all local ranks that was collected in that round and clear the rank list
        :return list: list of all neighbours local rank sent to this node
        """
        nlr = self.neighbour_loc_rank_buff
        self.neighbour_loc_rank_buff = []
        return nlr
