import requests
import json
from moviepy.editor import *
from moviepy.config import change_settings
import os
import firebase_admin
from firebase_admin import credentials, db
from datetime import datetime
import time
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2 import service_account
import pickle
import os.path
from google.auth.transport.requests import Request

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

def create_anime_video(anime_info):
    # Tạo tên file an toàn
    safe_title = sanitize_filename(anime_info['title'])
    output_filename = f"videos/{safe_title}.mp4"
    
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
                         font='Liberation-Sans',
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
                           font='Liberation-Sans',
                           align='west')
    synopsis_clip = synopsis_clip.set_position((image_width + 20, 150))
    synopsis_clip = synopsis_clip.set_duration(8)
    
    # Ghép tất c các clip vào background
    final_clip = CompositeVideoClip([background, 
                                   image_clip,
                                   title_clip,
                                   synopsis_clip])
    
    # Xuất video
    final_clip.write_videofile(output_filename,
                             fps=24,
                             codec='libx264')
    return output_filename

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

def sanitize_filename(filename):
    # Loại bỏ các ký tự đặc biệt trong tên file
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '')
    return filename.strip()

def get_youtube_credentials():
    SCOPES = ['https://www.googleapis.com/auth/youtube.upload']
    try:
        # Thử đọc token từ environment variable trước
        token_json = os.environ.get('OAUTH_TOKEN')
        
        # Nếu không có env var, thử đọc từ file local
        if not token_json and os.path.exists('oauth_token.json'):
            print("Đọc token từ file oauth_token.json")
            with open('oauth_token.json', 'r') as f:
                token_json = f.read()
        
        if token_json:
            token_data = json.loads(token_json)
            credentials = Credentials(
                token=token_data['token'],
                refresh_token=token_data['refresh_token'],
                token_uri=token_data['token_uri'],
                client_id=token_data['client_id'],
                client_secret=token_data['client_secret'],
                scopes=token_data['scopes']
            )
            
            # Tự động refresh nếu token hết hạn
            if credentials.expired:
                print("Token đã hết hạn, đang refresh...")
                credentials.refresh(Request())
                
                # Lưu lại token mới vào file local nếu đang chạy local
                if os.path.exists('oauth_token.json'):
                    token_data = {
                        'token': credentials.token,
                        'refresh_token': credentials.refresh_token,
                        'token_uri': credentials.token_uri,
                        'client_id': credentials.client_id,
                        'client_secret': credentials.client_secret,
                        'scopes': credentials.scopes
                    }
                    with open('oauth_token.json', 'w') as f:
                        json.dump(token_data, f)
                    print("Đã lưu token mới vào oauth_token.json")
                    
            return credentials
            
        # Nếu không có token, thực hiện xác thực mới
        print("Không tìm thấy token, bắt đầu xác thực mới...")
        flow = InstalledAppFlow.from_client_secrets_file(
            'client_secrets.json',
            scopes=SCOPES,
            redirect_uri='urn:ietf:wg:oauth:2.0:oob'
        )
        
        auth_url = flow.authorization_url(prompt='consent')
        print(f'Vui lòng truy cập URL này để xác thực:\n{auth_url[0]}')
        
        code = input('Nhập mã xác thực: ').strip()
        flow.fetch_token(code=code)
        credentials = flow.credentials
        
        # Lưu token mới vào file local
        token_data = {
            'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes
        }
        with open('oauth_token.json', 'w') as f:
            json.dump(token_data, f)
        print("Đã lưu token mới vào oauth_token.json")
        
        print("\nLưu JSON này vào GitHub Secret OAUTH_TOKEN:")
        print(json.dumps(token_data))
        
        return credentials
        
    except Exception as e:
        print(f"Chi tiết lỗi credentials: {str(e)}")
        raise e

def upload_to_youtube(video_path, title, description):
    try:
        credentials = get_youtube_credentials()
        youtube = build('youtube', 'v3', credentials=credentials)
        
        print("Đã khởi tạo YouTube service thành công")
        
        body = {
            'snippet': {
                'title': title,
                'description': description,
                'tags': ['anime', 'seasonal anime', 'anime preview'],
                'categoryId': '1'
            },
            'status': {
                'privacyStatus': 'private',
                'selfDeclaredMadeForKids': False
            }
        }

        print(f"Bắt đầu upload video: {title}")
        insert_request = youtube.videos().insert(
            part=','.join(body.keys()),
            body=body,
            media_body=MediaFileUpload(
                video_path, 
                chunksize=1024*1024, 
                resumable=True
            )
        )

        response = None
        while response is None:
            try:
                status, response = insert_request.next_chunk()
                if status:
                    print(f"Đã upload {int(status.progress() * 100)}%")
            except Exception as e:
                print(f"Lỗi trong quá trình upload chunk: {str(e)}")
                raise e

        print(f"Upload hoàn tất! Video ID: {response['id']}")
        return response['id']

    except Exception as e:
        print(f"Chi tiết lỗi upload: {str(e)}")
        raise e

def refresh_oauth_token():
    SCOPES = ['https://www.googleapis.com/auth/youtube.upload']
    flow = InstalledAppFlow.from_client_secrets_file(
        'client_secrets.json',
        scopes=SCOPES,
        redirect_uri='urn:ietf:wg:oauth:2.0:oob'
    )
    
    auth_url = flow.authorization_url(prompt='consent')
    print(f'Truy cập URL này:\n{auth_url[0]}')
    
    code = input('Nhập mã xác thực: ').strip()
    flow.fetch_token(code=code)
    
    # Lưu token
    with open('oauth_token.json', 'w') as f:
        json.dump({
            'token': flow.credentials.token,
            'refresh_token': flow.credentials.refresh_token,
            'token_uri': flow.credentials.token_uri,
            'client_id': flow.credentials.client_id,
            'client_secret': flow.credentials.client_secret,
            'scopes': flow.credentials.scopes
        }, f)
    
    print('Token đã được lưu vào oauth_token.json')

def main():
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
                
                # Upload lên YouTube
                video_title = f"{anime_info['title']} - Anime Preview"
                video_description = anime_info['synopsis']
                youtube_video_id = upload_to_youtube(video_path, video_title, video_description)
                
                # Lưu thêm YouTube video ID vào database
                save_to_database(anime_id, anime_info, video_path, youtube_video_id)
                
                print(f"Đã hoàn thành xử lý và upload anime: {anime['title']}")
                break
            else:
                print(f"Anime {anime['title']} đã tồn tại trong database")
                
        except Exception as e:
            print(f"Lỗi khi xử lý anime {anime['title']}: {e}")
            continue

if __name__ == "__main__":
    main()