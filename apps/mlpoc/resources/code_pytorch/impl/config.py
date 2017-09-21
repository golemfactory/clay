# iris config
# iris has 100 samples, minus 0.2*100 = 20 test gets us 80
# which is 4 batches for epoch
IRIS_SIZE = 80
BATCH_SIZE = 20
NUM_CLASSES = 3
TEST_SIZE = 0.2

# neural net config
LEARNING_RATE = 0.01
NUM_EPOCHS = 10

# system config
# not used yet, but it should be possible to change
# ARCH from CPU to GPU in the future
ARCH = "CPU"

# randomness config
SEED = 42
