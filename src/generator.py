import os
import requests
from PIL import Image, ImageDraw

def create_card():
    # 1. 이미지 생성 (기존 로직)
    img = Image.new('RGB', (1080, 1080), color=(73, 80, 243))
    draw = ImageDraw.Draw(img)
    draw.text((400, 500), "Auto Post Success!", fill=(255, 255, 255))
    
    if not os.path.exists("images"):
        os.makedirs("images")
    
    save_path = "images/result.png"
    img.save(save_path)
    print("이미지 생성 완료")

def upload_to_instagram():
    # 2. GitHub Secrets에서 정보 가져오기
    access_token = os.getenv('INSTA_ACCESS_TOKEN')
    account_id = os.getenv('INSTA_USER_ID')
    caption = os.getenv('INSTA_CAPTION', 'Default Caption')
    
    # 3. 인스타그램 API는 "인터넷에 공개된 이미지 주소"가 필요합니다.
    # 자신의 GitHub 유저네임과 저장소 이름을 여기에 맞게 수정하세요.
    # 예: https://raw.githubusercontent.com/유저명/저장소명/main/images/result.png
    user_name = "bomhi"
    repo_name = "insta-automation"
    image_url = f"https://raw.githubusercontent.com/bomhi/insta-automation/main/images/result.png"

    # A. 미디어 컨테이너 생성
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
        # B. 실제 게시물 업로드
        publish_url = f"https://graph.facebook.com/v19.0/{account_id}/media_publish"
        publish_payload = {
            'creation_id': creation_id,
            'access_token': access_token
        }
        publish_res = requests.post(publish_url, data=publish_payload)
        print("인스타그램 게시 성공!", publish_res.json())
    else:
        print("업로드 실패:", res_data)

if __name__ == "__main__":
    create_card()
    # Secrets 값이 설정되어 있을 때만 업로드 실행
    if os.getenv('INSTA_ACCESS_TOKEN') and os.getenv('INSTA_USER_ID'):
        upload_to_instagram()
