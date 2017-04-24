
def estimate_time(test_time, test_resolution, expected_resolution, test_spp, spp):
    test_pixels = test_resolution[0] * test_resolution[1]
    final_pixels = expected_resolution[0] * expected_resolution[1]
    return (final_pixels / test_pixels) * test_time * (spp / test_spp)