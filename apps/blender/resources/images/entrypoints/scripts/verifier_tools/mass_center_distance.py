from PIL import Image
import sys


class MetricMassCenterDistance:

    @staticmethod
    def compute_metrics(image1, image2):
        if image1.size != image2.size:
            raise Exception("Image sizes differ")
        mass_centers_1 = MetricMassCenterDistance.compute_mass_centers(image1)
        mass_centers_2 = MetricMassCenterDistance.compute_mass_centers(image2)
        max_x_distance = 0
        max_y_distance = 0
        for channel_index in mass_centers_1.keys():
            x1, y1 = mass_centers_1[channel_index]
            x2, y2 = mass_centers_2[channel_index]
            x_distance = abs(x1 - x2)
            y_distance = abs(y1 - y2)
            max_x_distance = max(max_x_distance, x_distance)
            max_y_distance = max(max_y_distance, y_distance)
        return {
            "max_x_mass_center_distance": max_x_distance,
            "max_y_mass_center_distance": max_y_distance
                }

    @staticmethod
    def get_labels():
        return ["max_x_mass_center_distance", "max_y_mass_center_distance"]

    @staticmethod
    def compute_mass_centers(image):
        image = image.convert('RGB')
        pixels = image.load()
        width, height = image.size
        results = dict()
        for channel_index in range(len(pixels[0, 0])):
            mass_center_x = 0
            mass_center_y = 0
            total_mass = 0
            for x in range(width):
                for y in range(height):
                    mass = pixels[x, y][channel_index]
                    mass_center_x += mass * x
                    mass_center_y += mass * y
                    total_mass += mass
                    
            divisor_x = (float(total_mass) * width)
            divisor_y = (float(total_mass) * height)
               
            if divisor_x == 0:
                mass_center_x = 0.5
            else:
                mass_center_x = mass_center_x / divisor_x
                
            if divisor_y == 0:
                mass_center_y = 0.5
            else:
                mass_center_y = mass_center_y / divisor_y
            
            results[channel_index] = mass_center_x, mass_center_y        
        return results


def run():
    first_image = Image.open(sys.argv[1])
    second_image = Image.open(sys.argv[2])

    mass_center_distance = MetricMassCenterDistance()

    print(mass_center_distance.compute_metrics(first_image, second_image))


if __name__ == "__main__":
    run()
