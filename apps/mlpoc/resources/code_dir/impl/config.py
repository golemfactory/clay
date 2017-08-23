from hashlib import sha3_256 as hashing_algorithm

# iris config
# iris has 100 samples, minus 0.2*100 = 20 test gets us 80, which is 4 batches for epoch
STEPS_PER_EPOCH = 4
IRIS_SIZE = 80
BATCH_SIZE = 20
NUM_CLASSES = 3
TEST_SIZE = 0.2

# serialized config
SHARED_PATH = "/home/jacek/tests/T1"
SAVE_MODEL_AS_DICT = True

# neural net config
LEARNING_RATE = 0.01
NUM_EPOCHS = 10
HIDDEN_SIZE = 10
ARCH = "CPU"

# hashing config
HASHING_ALGORITHM = hashing_algorithm
# digest size computation
MAX_LAST_BYTES_NUM = hashing_algorithm(b"something").digest_size
