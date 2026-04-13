import os
import requests
import time  # 1. 시간 대기 기능을 위해 추가
from PIL import Image, ImageDraw, ImageFont

def create_card():
    # 1. 이미지 생성
    width, height = 1080, 1080
    img = Image.new('RGB', (width, height), color=(100, 50, 255))
    draw = ImageDraw.Draw(img)
    
    text = "오늘의 자동화 성공!\nGitHub Actions 완료"
    
    try:
        # 폰트 파일이 없을 경우 대비
        font = ImageFont.load_default()
    except:
        font = None

    # 중앙에 텍스트 그리기
    draw.text((width//2, height//2), text, fill=(255, 255, 255), anchor="mm", align="center")
    
    if not os.path.exists("images"):
        os.makedirs("images")
    
    img.save("images/result.png")
    print("이미지 생성 완료: images/result.png")

def upload_to_instagram():
    # 2. GitHub Secrets에서 정보 가져오기
    access_token = os.getenv('INSTA_ACCESS_TOKEN')
    account_id = os.getenv('INSTA_USER_ID')
    caption = os.getenv('INSTA_CAPTION', 'GitHub Actions로 자동 게시된 포스트입니다! #coding #automation')
    
    # 본인의 정보로 꼭 수정하세요!
    user_name = "bomhi" 
    repo_name = "insta-automation"
    image_url = f"https://raw.githubusercontent.com/bomhi/insta-automation/main/images/result.png"

    print(f"업로드 시도 중... 이미지 URL: {image_url}")

    # A. 미디어 컨테이너 생성 (인스타 서버에 이미지 알리기)
    post_url = f"https://graph.facebook.com/v19.0/{account_id}/media"
    payload = {
        'image_url': image_url,
        'caption': caption,
        'access_token': access_token
    }
    response = requests.post(post_url, data=payload)
    res_data = response.json()
    
    if 'id' in res_data:
        creation_id = res_data['id']
        
        # --- 핵심 수정 부분: 인스타 서버가 이미지를 처리할 시간을 줍니다 ---
        print("인스타그램 서버가 이미지를 처리 중입니다... 10초간 대기합니다.")
        time.sleep(10) 
        # ---------------------------------------------------------
        
        # B. 실제 게시물 업로드 승인
        publish_url = f"https://graph.facebook.com/v19.0/{account_id}/media_publish"
        publish_payload = {
            'creation_id': creation_id,
            'access_token': access_token
        }
        publish_res = requests.post(publish_url, data=publish_payload)
        print("인스타그램 게시 최종 성공!", publish_res.json())
    else:
        print("업로드 단계 1 실패:", res_data)

if __name__ == "__main__":
    # 1. 그림 그리기 실행
    create_card()
    # 2. 인스타 업로드 실행
    upload_to_instagram()
