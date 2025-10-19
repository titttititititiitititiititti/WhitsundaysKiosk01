import os
import shutil

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.JPG', '.JPEG', '.PNG', '.WEBP'}

base_dir = os.path.join('static', 'tour_images')

for company in os.listdir(base_dir):
    company_path = os.path.join(base_dir, company)
    if not os.path.isdir(company_path):
        continue
    for tour in os.listdir(company_path):
        tour_path = os.path.join(company_path, tour)
        if not os.path.isdir(tour_path):
            continue
        # Find all image files
        images = [f for f in os.listdir(tour_path)
                  if os.path.splitext(f)[1] in IMAGE_EXTENSIONS and os.path.isfile(os.path.join(tour_path, f))]
        if not images:
            continue
        # Find the largest image
        largest_image = max(images, key=lambda f: os.path.getsize(os.path.join(tour_path, f)))
        largest_image_path = os.path.join(tour_path, largest_image)
        ext = os.path.splitext(largest_image)[1]
        thumbnail_path = os.path.join(tour_path, f'thumbnail{ext}')
        # Remove existing thumbnail if it exists (with any extension)
        for ext_check in IMAGE_EXTENSIONS:
            thumb_candidate = os.path.join(tour_path, f'thumbnail{ext_check}')
            if os.path.exists(thumb_candidate):
                os.remove(thumb_candidate)
        # Rename the largest image to thumbnail
        if largest_image_path != thumbnail_path:
            shutil.move(largest_image_path, thumbnail_path)
        print(f'Set thumbnail for {tour_path} to {thumbnail_path}') 