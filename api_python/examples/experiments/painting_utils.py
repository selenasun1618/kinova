import cv2
import numpy as np
from sklearn.cluster import KMeans
from PIL import Image
import matplotlib.pyplot as plt

# CONSTANTS
NUM_COLORS = 3
STROKE_SIZE = 0.5 # in
RESOLUTION = 1 / STROKE_SIZE # ppi
CANVAS_DIM_X = 11 # in
CANVAS_DIM_Y = 8.5 # in

STROKE_SIZE_PIXELS = int(STROKE_SIZE * RESOLUTION) # old

def preprocessing(image_path):
    original_image = cv2.imread(image_path)
    original_image = original_image.astype(np.float32) / 255.0 #convert to float

    # Rotate image to match canvas orientation
    is_img_landscape = original_image.shape[0] <= original_image.shape[1] #  landscape = 1, portrait = 0
    is_canvas_landscape = CANVAS_DIM_X <= CANVAS_DIM_Y # landscape = 1, portrait = 0
    if is_img_landscape ^ is_canvas_landscape: # xor
        print("rotated")
        original_image = cv2.rotate(original_image, cv2.ROTATE_90_COUNTERCLOCKWISE)
        # Resize image to match canvas resolution
        resized_image = cv2.resize(original_image, (int(RESOLUTION * CANVAS_DIM_Y), int(RESOLUTION * CANVAS_DIM_X)))  # Resize images
    else:
        resized_image = cv2.resize(original_image, (int(RESOLUTION * CANVAS_DIM_Y), int(RESOLUTION * CANVAS_DIM_X)))

    cv2.imshow('resized image', resized_image)

    print(f'img size: {original_image.shape}')
    print(f'resized img size: {resized_image.shape}')

    return resized_image

def apply_kmeans(image, num_clusters=NUM_COLORS):

    # Reshape image for KMeans clustering
    rows, cols, channels = image.shape

    pixels = image.reshape((-1, channels)) #each pixel's RGB values are concatenated into a single vector, flatten image

    # Apply KMeans clustering
    kmeans = KMeans(n_clusters=num_clusters, random_state=42)
    kmeans.fit(pixels)

    cluster_labels = kmeans.labels_ #index of cluster each pixel belongs to
    cluster_centers = kmeans.cluster_centers_

    # Convert the colors to uint8 format (required for displaying with OpenCV)
    # cluster_centers = cluster_centers.astype(np.uint8) #coordinates of cluster centers

    # Display the representative colors
    print("displaying")
    for i, color in enumerate(cluster_centers):
        color_swatch = np.zeros((100, 100, 3), dtype=np.uint8)
        color_swatch[:, :] = color*255
        print(f'Color {i + 1}: {color*255}')
        cv2.imshow(f'Color {i + 1}', color_swatch)

    return cluster_labels, cluster_centers


def draw_straight_strokes(image, cluster_labels, cluster_centers, num_colors=NUM_COLORS, stroke_size=STROKE_SIZE):
    # Draw vertical lines in different colors

    # 1) Assign every STROKE_SIZE x STROKE_SIZE block a color
    output_image = np.zeros_like(image)
    rows, cols, channels = image.shape
    strokes = []
    colors = []

    for cluster_id in range(num_colors): #for each color
        cluster_indices = np.where(cluster_labels == cluster_id)[0]
        cluster_color = cluster_centers[cluster_id] * 255
        cluster_color = (int(cluster_color[0]), int(cluster_color[1]), int(cluster_color[2]))

        points_of_color = []
        for index in cluster_indices: #for all points in color
            y, x = np.unravel_index(index, (rows, cols))
            point = (x,y)
            points_of_color.append(point)
        sorted_points = sorted(points_of_color, key=lambda k: [k[0], k[1]])

        cols_in_color = set([point[0] for point in sorted_points])
        for c in cols_in_color:
            relevant_points = [point for point in sorted_points if point[0]==c]
            start = relevant_points[0]
            for i in range(1, len(relevant_points)):
                if relevant_points[i][1] != relevant_points[i - 1][1] + 1: #if not consecutive
                    end = relevant_points[i - 1]
                    strokes.append((start, end, cluster_color))
                    cv2.line(output_image, start, end, cluster_color, 1)

                    start = relevant_points[i]

            # Add the last range
            strokes.append((start, relevant_points[-1], cluster_color))
            colors.append(cluster_color)
            cv2.line(output_image, start, relevant_points[-1], cluster_color, 1)

    return output_image, strokes, colors


def draw_strokes(image, cluster_labels, cluster_centers, num_colors=NUM_COLORS, stroke_size=STROKE_SIZE_PIXELS):
    # Create a new canvas to draw strokes
    output_image = np.zeros_like(image)
    rows, cols, channels = image.shape
    start_end_points = []


    for cluster_id in range(num_colors):
        print(cluster_id)
        cluster_indices = np.where(cluster_labels == cluster_id)[0]
        cluster_color = cluster_centers[cluster_id]

        for index in cluster_indices:
            y, x = np.unravel_index(index, (rows, cols))
            end_point = (x,y)

            # Introduce randomness to stroke color
            paint_color = cluster_color + np.random.uniform(-0.0001, 0.0001, size=3)

            # Introduce randomness to stroke size
            # stroke_size = np.random.randint(2, 8)

            # METHOD 1: circle stroke
            # cv2.circle(output_image, (x, y), stroke_size, paint_color, -1)

            #METHOD 2: line strik

            # Stroke size based on color intensity. Higher intensity = thicker strokes
            # intensity = np.mean(cluster_color)
            # stroke_size = int(3 + intensity)  # Adjust factors

            # Stroke direction based on color channel values
            direction = np.array([cluster_color[2] - cluster_color[0], cluster_color[1] - cluster_color[0]])
            direction /= np.linalg.norm(direction) #normalize to unit vector

            # Starting point of the stroke, offset from (x,y) by half of stroke size
            start_point = (x - int(stroke_size * direction[0] * 0.5), y - int(stroke_size * direction[1] * 0.5))

            # Paint stroke with a line
            cv2.line(output_image, start_point, end_point, paint_color, stroke_size)

            start_end_points.append([start_point, end_point]) #data structure with list of start/end points

    return output_image, start_end_points

def pixel_to_physical_coords(pixel_coords, ROBOT_ORIGIN):
    physical_coords = []
    # [(start_x, start_y, start_z, thetax, thetay, thetaz), (end_x, end_y, end_z, thetax, thetay, thetaz), (r, g, b))]
    for i in range(len(pixel_coords)):
        start_x, start_y = pixel_coords[i][0]
        end_x, end_y = pixel_coords[i][1]
        cur = []
        cur.append((start_x * STROKE_SIZE + ROBOT_ORIGIN[0], start_y * STROKE_SIZE + ROBOT_ORIGIN[1], ROBOT_ORIGIN[2], ROBOT_ORIGIN[3], ROBOT_ORIGIN[4], ROBOT_ORIGIN[5]))
        cur.append((end_x * STROKE_SIZE + ROBOT_ORIGIN[0], end_y * STROKE_SIZE + ROBOT_ORIGIN[1],ROBOT_ORIGIN[2], ROBOT_ORIGIN[3], ROBOT_ORIGIN[4], ROBOT_ORIGIN[5]))
        cur.append(pixel_coords[i][2])
        physical_coords.append(cur)
    return physical_coords

def painting(image_path, save_path, ROBOT_ORIGIN):

    resized_image = preprocessing(image_path)

    labels, centers = apply_kmeans(resized_image)
    output_image, start_end_points, colors = draw_straight_strokes(resized_image, labels, centers)

    physical_coords = pixel_to_physical_coords(start_end_points, ROBOT_ORIGIN)

    # Display painting
    # cv2.imshow('Stroke-Based Painting', output_image/255)
    cv2.imwrite(save_path, output_image)

    scaled_img = Image.open(save_path)
    scaled_img = scaled_img.resize((int(RESOLUTION * CANVAS_DIM_Y * 100), int(RESOLUTION * CANVAS_DIM_X * 100)))
    scaled_img_cv2 = cv2.cvtColor(np.array(scaled_img), cv2.COLOR_RGB2BGR)
    cv2.imshow('Scaled Painting', scaled_img_cv2)
    cv2.waitKey(0)
    cv2.destroyAllWindows()

    print(f'num strokes: {len(start_end_points)}')
    return physical_coords, colors

def main():
    image_path = 'stanford_logo.png'
    save_path = 'stanford_painting.png'
    ROBOT_ORIGIN = (0.48, -.117, .177, 90, 0, 90) # TODO CHANGE
    physical_coords = painting(image_path, save_path, ROBOT_ORIGIN)

if __name__ == '__main__':
    main()