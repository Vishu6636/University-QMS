import os
from PIL import Image

def optimize_images():
    source_dir = r"C:\Users\sriva_3b9ej2a\Downloads"
    dest_dir = r"c:\Users\sriva_3b9ej2a\OneDrive\Documents\projects\university-query-system\app\assets\backgrounds"
    os.makedirs(dest_dir, exist_ok=True)
    
    images = [
        "bg_landing.png",
        "bg_onboarding.png",
        "bg_public_inquiry.png",
        "bg_super_admin.png",
        "bg_admin.png",
        "bg_student.png"
    ]
    
    print("Starting background images optimization...")
    print("-" * 60)
    
    for img_name in images:
        src_path = os.path.join(source_dir, img_name)
        if not os.path.exists(src_path):
            print(f"Error: {src_path} does not exist.")
            continue
            
        orig_size = os.path.getsize(src_path) / (1024 * 1024)
        
        with Image.open(src_path) as img:
            width, height = img.size
            print(f"Processing {img_name}: {width}x{height} ({orig_size:.2f} MB)")
            
            # Resize if width > 1920
            if width > 1920:
                new_width = 1920
                new_height = int(height * (1920 / width))
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                print(f"  Resized to: {new_width}x{new_height}")
            
            # Output file name: change .png to .webp
            dest_name = os.path.splitext(img_name)[0] + ".webp"
            dest_path = os.path.join(dest_dir, dest_name)
            
            # Save as optimized WebP
            img.save(dest_path, "WEBP", quality=80)
            
            dest_size = os.path.getsize(dest_path) / 1024
            print(f"  Saved to {dest_name}: {dest_size:.1f} KB")
            reduction = (1 - (os.path.getsize(dest_path) / os.path.getsize(src_path))) * 100
            print(f"  Size reduction: {reduction:.1f}%")
            print("-" * 60)

if __name__ == "__main__":
    optimize_images()
