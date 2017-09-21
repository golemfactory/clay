from abc import ABCMeta, abstractmethod


class BatchManager(metaclass=ABCMeta):

    def __iter__(self):
        return self

    @abstractmethod
    def __next__(self) -> ('np.ndarray', 'np.ndarray'):
        """
        Return next batch of input
        :return: (training instances, answers)
        """
        pass

    @abstractmethod
    def save(self, batch_num: int, filepath: str):
        """
        saves itself, to be later restored in verification process
        :param batch_num: current batch number
        :param filepath: where to save itself
        :return:
        """
        pass

    @abstractmethod
    def get_input_size(self) -> int:
        """
        Returns size of one row of input - that's how wide the model is
        :return: input size
        """
        pass

    @abstractmethod
    def get_full_training_set(self) -> ('np.ndarray', 'np.ndarray'):
        """
        Returns full training set
        :return: (training instances, answers)
        """
        pass

    @abstractmethod
    def get_order_of_batches(self):
        """
        Returns order of batches, eg something that can be casted to list of indices
        :return: List-like object containing order of batches
        """
        pass

    def get_full_testing_set(self) -> ('np.ndarray', 'np.ndarray'):
        """
        Returns full testing set, intersection with data returned
        from get_full_training_set should be empty
        :return: (testing_instances, answers)
        """
        pass