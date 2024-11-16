import requests
from moviepy.editor import *
from moviepy.config import change_settings
import os
import firebase_admin
from firebase_admin import credentials, db
from datetime import datetime
import time
import os.path
from google.auth.transport.requests import Request
from youtube_uploader import upload_to_youtube  # Thêm dòng này
from video_processor import create_anime_video  # Thêm dòng này

# Thêm dòng này vào đầu file (thay đổi đường dẫn theo máy của bạn)
change_settings({"IMAGEMAGICK_BINARY": r"C:\Program Files\ImageMagick-7.1.1-Q16-HDRI\magick.exe"})

# Khởi tạo Firebase
cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://animeytb-9ddc8-default-rtdb.asia-southeast1.firebasedatabase.app/'
})

def get_anime_info(anime_id):
    # Gọi Jikan API
    url = f"https://api.jikan.moe/v4/anime/{anime_id}"
    response = requests.get(url)
    data = response.json()
    
    return data['data']

def get_seasonal_anime():
    # Thêm timeout và retry
    try:
        url = f"https://api.jikan.moe/v4/seasons/2024/summer"
        response = requests.get(url, timeout=30)
        data = response.json()
        return [anime for anime in data['data'] if anime['type'] == 'TV']
    except requests.exceptions.RequestException as e:
        print(f"Lỗi khi kết nối với API: {e}")
        time.sleep(5)  # Đợi 5 giây trước khi thử lại
        return get_seasonal_anime()  # Thử lại

def check_anime_in_database(anime_id):
    # Kiểm tra xem anime đã có trong database chưa
    ref = db.reference(f'/anime/{anime_id}')
    return ref.get() is not None

def save_to_database(anime_id, anime_info, video_path, youtube_video_id):
    # Lưu thông tin anime và đường dẫn video vào database
    ref = db.reference(f'/anime/{anime_id}')
    ref.set({
        'title': anime_info['title'],
        'synopsis': anime_info['synopsis'],
        'video_path': video_path,
        'youtube_video_id': youtube_video_id,
        'created_at': datetime.now().isoformat()
    })

def main(upload_to_youtube_enabled=False):
    # Tạo thư mục videos nếu chưa tồn tại
    if not os.path.exists('videos'):
        os.makedirs('videos')
        
    seasonal_anime = get_seasonal_anime()
    
    # Tìm anime đầu tiên chưa được xử lý
    for anime in seasonal_anime:
        try:
            anime_id = anime['mal_id']
            
            if not check_anime_in_database(anime_id):
                print(f"Đang xử lý anime: {anime['title']}")
                
                anime_info = get_anime_info(anime_id)
                video_path = create_anime_video(anime_info)
                
                youtube_video_id = None
                if upload_to_youtube_enabled:
                    # Upload lên YouTube nếu được bật
                    video_title = f"{anime_info['title']} - Anime Preview"
                    video_description = anime_info['synopsis']
                    youtube_video_id = upload_to_youtube(video_path, video_title, video_description)
                    print(f"Đã upload video lên YouTube với ID: {youtube_video_id}")
                else:
                    print("Bỏ qua bước upload YouTube (đã tắt)")
                
                save_to_database(anime_id, anime_info, video_path, youtube_video_id)
                
                print(f"Đã hoàn thành xử lý anime: {anime['title']}")
                break
            else:
                print(f"Anime {anime['title']} đã tồn tại trong database")
                
        except Exception as e:
            print(f"Lỗi khi xử lý anime {anime['title']}: {e}")
            continue

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Tạo và upload video anime preview')
    parser.add_argument('--upload', 
                       action='store_true',
                       help='Bật tính năng upload lên YouTube')
    
    args = parser.parse_args()
    main(upload_to_youtube_enabled=args.upload)