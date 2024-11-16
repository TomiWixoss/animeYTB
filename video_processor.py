from moviepy.editor import *
import requests
import os

def create_anime_video(anime_info):
    # Tạo tên file an toàn
    safe_title = sanitize_filename(anime_info['title'])
    output_filename = f"videos/{safe_title}.mp4"
    
    # Tải ảnh từ URL
    image_url = anime_info['images']['jpg']['large_image_url']
    response = requests.get(image_url)
    with open("temp_image.jpg", "wb") as f:
        f.write(response.content)
    
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
    
    # Xử lý tiêu đề
    title_width = W - image_width - 40
    title_clip = TextClip(anime_info['title'], 
                         fontsize=50,
                         color='white',
                         size=(title_width, None),
                         method='caption',
                         font='Liberation-Sans',
                         align='west')
    title_clip = title_clip.set_position((image_width + 20, 50))
    title_clip = title_clip.set_duration(8)
    
    # Xử lý synopsis
    synopsis_text = anime_info['synopsis']
    if len(synopsis_text) > 500:
        synopsis_text = synopsis_text[:500] + "..."
    
    synopsis_clip = TextClip(synopsis_text,
                           fontsize=30,
                           color='white',
                           size=(title_width, None),
                           method='caption',
                           font='Liberation-Sans',
                           align='west')
    synopsis_clip = synopsis_clip.set_position((image_width + 20, 150))
    synopsis_clip = synopsis_clip.set_duration(8)
    
    # Ghép tất cả các clip
    final_clip = CompositeVideoClip([background, 
                                   image_clip,
                                   title_clip,
                                   synopsis_clip])
    
    # Xuất video
    final_clip.write_videofile(output_filename,
                             fps=24,
                             codec='libx264')
    return output_filename

def sanitize_filename(filename):
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '')
    return filename.strip()