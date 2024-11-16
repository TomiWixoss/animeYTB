import requests
import json
from moviepy.editor import *
from moviepy.config import change_settings
import os

# Thêm dòng này vào đầu file (thay đổi đường dẫn theo máy của bạn)
change_settings({"IMAGEMAGICK_BINARY": r"C:\Program Files\ImageMagick-7.1.1-Q16-HDRI\magick.exe"})

def get_anime_info(anime_id):
    # Gọi Jikan API
    url = f"https://api.jikan.moe/v4/anime/{anime_id}"
    response = requests.get(url)
    data = response.json()
    
    return data['data']

def create_anime_video(anime_info):
    # Tải ảnh từ URL
    image_url = anime_info['images']['jpg']['large_image_url']
    response = requests.get(image_url)
    with open("temp_image.jpg", "wb") as f:
        f.write(response.content)
        
    # Tạo clip từ ảnh
    image_clip = ImageClip("temp_image.jpg")
    
    # Thay đổi kích thước ảnh một cách đơn giản
    image_width = 1920  # Full HD width
    current_w, current_h = image_clip.size
    new_h = int(current_h * (image_width / current_w))
    image_clip = image_clip.resize((image_width, new_h))
    
    # Thay đổi đường dẫn ImageMagick cho Linux
    if os.name != 'nt':  # Nếu không phải Windows
        change_settings({"IMAGEMAGICK_BINARY": "convert"})
    
    # Thiết lập kích thước video và background
    W, H = 1280, 720
    background = ColorClip(size=(W, H), color=(0, 0, 0))
    background = background.set_duration(8)
    
    # Xử lý ảnh (chiếm 40% chiều rộng màn hình)
    image_width = int(W * 0.4)
    image_clip = ImageClip("temp_image.jpg")
    image_clip = image_clip.resize(width=image_width)
    if image_clip.h > H:
        image_clip = image_clip.resize(height=H)
    image_clip = image_clip.set_position(('left', 'center'))
    image_clip = image_clip.set_duration(8)
    
    # Xử lý tiêu đề (bên phải, phía trên)
    title_width = W - image_width - 40  # Trừ đi padding
    title_clip = TextClip(anime_info['title'], 
                         fontsize=50,
                         color='white',
                         size=(title_width, None),
                         method='caption',
                         align='west')
    title_clip = title_clip.set_position((image_width + 20, 50))
    title_clip = title_clip.set_duration(8)
    
    # Xử lý synopsis (bên phải, phía dưới tiêu đề)
    synopsis_text = anime_info['synopsis']
    if len(synopsis_text) > 500:
        synopsis_text = synopsis_text[:500] + "..."
    
    synopsis_clip = TextClip(synopsis_text,
                           fontsize=30,
                           color='white',
                           size=(title_width, None),
                           method='caption',
                           align='west')
    synopsis_clip = synopsis_clip.set_position((image_width + 20, 150))
    synopsis_clip = synopsis_clip.set_duration(8)
    
    # Ghép tất cả các clip vào background
    final_clip = CompositeVideoClip([background, 
                                   image_clip,
                                   title_clip,
                                   synopsis_clip])
    
    # Xuất video
    final_clip.write_videofile(f"{anime_info['title']}.mp4",
                             fps=24,
                             codec='libx264')

def main():
    # Ví dụ với ID của anime Naruto
    anime_id = 20
    anime_info = get_anime_info(anime_id)
    create_anime_video(anime_info)

if __name__ == "__main__":
    main()