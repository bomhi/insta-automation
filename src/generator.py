import os
import requests
import time
from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFont
from deep_translator import GoogleTranslator

def get_overseas_news():
    api_key = os.getenv('NEWS_API_KEY')
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    
    # 해외(영어) 뉴스 중 가장 인기 있는 뉴스 1개 가져오기
    url = f"https://newsapi.org/v2/everything?q=world&language=en&from={yesterday}&sortBy=popularity&pageSize=1&apiKey={api_key}"
    
    try:
        response = requests.get(url)
        data = response.json()
        if data.get('status') == 'ok' and data.get('articles'):
            return data['articles'][0]
    except Exception as e:
        print(f"뉴스 수집 실패: {e}")
    return None

def translate_content(text):
    try:
        # 영어를 한국어로 번역
        return GoogleTranslator(source='en', target='ko').translate(text)
    except:
        return text

def create_card(title_ko):
    width, height = 1080, 1080
    img = Image.new('RGB', (width, height), color=(15, 15, 15)) # 다크 배경
    draw = ImageDraw.Draw(img)
    
    # 텍스트 강조 디자인
    label = "GLOBAL TRENDING NEWS"
    
    try:
        # 폰트가 없다면 기본 사용 (가급적 나눔스퀘어 같은 .ttf 파일을 저장소에 올리는 걸 추천)
        font = ImageFont.load_default()
    except:
        font = None

    # 상단 라벨 (초록색 포인트)
    draw.text((width//2, 150), label, fill=(0, 255, 127), anchor="mm")
    
    # 메인 제목 (크게, 상단 배치)
    # 제목이 길면 자동 줄바꿈 (대략 15자 기준)
    wrapped_title = ""
    for i in range(0, len(title_ko), 15):
        wrapped_title += title_ko[i:i+15] + "\n"

    draw.text((width//2, 400), wrapped_title.strip(), fill=(255, 255, 255), anchor="mm", align="center", spacing=20)
    
    if not os.path.exists("images"):
        os.makedirs("images")
    img.save("images/result.png")
    print("이미지 생성 완료")

def upload_to_instagram(summary_text):
    access_token = os.getenv('INSTA_ACCESS_TOKEN')
    account_id = os.getenv('INSTA_USER_ID')
    
    # 인스타그램 본문 내용 구성 (요약 10줄 이내 + 해시태그)
    caption = f"🌍 오늘의 해외 뉴스 요약\n\n{summary_text}\n\n#해외 #뉴스 #세계뉴스 #자동화 #TechNews"
    
    user_name = "bomhi" 
    repo_name = "insta-automation"
    image_url = f"https://raw.githubusercontent.com/{user_name}/{repo_name}/main/images/result.png"

    # 1. 미디어 컨테이너 생성
    post_url = f"https://graph.facebook.com/v19.0/{account_id}/media"
    res = requests.post(post_url, data={'image_url': image_url, 'caption': caption, 'access_token': access_token}).json()
    
    if 'id' in res:
        creation_id = res['id']
        print("서버 처리 대기 중(20초)...")
        time.sleep(20)
        
        # 2. 실제 게시
        publish_url = f"https://graph.facebook.com/v19.0/{account_id}/media_publish"
        publish_res = requests.post(publish_url, data={'creation_id': creation_id, 'access_token': access_token}).json()
        print("인스타그램 업로드 성공:", publish_res)
    else:
        print("업로드 실패:", res)

if __name__ == "__main__":
    # 1. 뉴스 가져오기
    article = get_overseas_news()
    
    if article:
        # 2. 번역 (제목 및 요약용 설명)
        title_ko = translate_content(article['title'])
        desc_ko = translate_content(article['description'])
        
        # 3. 이미지 생성 (제목 위주)
        create_card(title_ko)
        
        # 4. 요약 정리 (10줄 이내)
        summary = f"📍 제목: {title_ko}\n\n📝 요약: {desc_ko[:200]}..." # 간단 요약
        
        # 5. 업로드
        upload_to_instagram(summary)
    else:
        print("가져온 뉴스가 없습니다.")
