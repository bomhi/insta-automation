import os
import requests
import time
from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
from deep_translator import GoogleTranslator

# 1. 뉴스 데이터 수집 및 번역 (로그용 비교 데이터 생성)
def get_processed_news():
    api_key = os.getenv('NEWS_API_KEY')
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    url = f"https://newsapi.org/v2/everything?q=world&language=en&from={yesterday}&sortBy=popularity&pageSize=1&apiKey={api_key}"
    
    try:
        data = requests.get(url).json()
        if not data.get('articles'): return None
        
        article = data['articles'][0]
        translator = GoogleTranslator(source='en', target='ko')
        
        # 원문과 번역본 준비
        en_title = article['title']
        en_desc = article['description']
        ko_title = translator.translate(en_title)
        ko_desc = translator.translate(en_desc)
        
        # 10줄 이내 가독성 요약 (인스타 업로드용)
        summary_ko = f"📍 {ko_title}\n\n"
        sentences = ko_desc.split('. ')
        for s in sentences[:4]: # 핵심 문장 4개 추출
            if len(s) > 5:
                summary_ko += f"• {s.strip()}\n"
        
        # 깃허브 로그 확인용 (인스타에는 안 올라감)
        print("\n" + "="*50)
        print("[번역 품질 체크 로딩]")
        print(f"원문 제목: {en_title}")
        print(f"번역 제목: {ko_title}")
        print(f"원문 내용: {en_desc[:100]}...")
        print(f"번역 내용: {ko_desc[:100]}...")
        print("="*50 + "\n")

        return {
            'ko_title': ko_title,
            'summary_ko': summary_ko,
            'image_url': article.get('urlToImage')
        }
    except Exception as e:
        print(f"데이터 처리 오류: {e}")
        return None

# 2. 이미지 생성 (1번: 블러+제목, 2~3번: 사진만)
def create_slides(article):
    width, height = 1080, 1080
    bg_url = article['image_url']
    image_paths = []

    try:
        raw_img = Image.open(requests.get(bg_url, stream=True).raw).convert('RGB')
    except:
        raw_img = Image.new('RGB', (width, height), color=(30, 30, 30))

    for i in range(3):
        slide = raw_img.copy().resize((width, height), Image.Resampling.LANCZOS)
        if i == 0: # 첫 장만 특수 효과
            slide = slide.filter(ImageFilter.GaussianBlur(radius=15))
            slide = ImageEnhance.Brightness(slide).enhance(0.5)
            draw = ImageDraw.Draw(slide)
            try:
                font = ImageFont.truetype("NanumSquareR.ttf", 80)
            except:
                font = ImageFont.load_default()
            
            # 제목 줄바꿈
            text = article['ko_title']
            wrapped = "".join([text[j:j+12] + "\n" for j in range(0, len(text), 12)])
            draw.text((width//2, height//2), wrapped.strip(), fill=(255,255,255), font=font, anchor="mm", align="center")
        
        path = f"images/slide_{i}.png"
        slide.save(path)
        image_paths.append(path)
    return image_paths

def main():
    # 실행 인자 확인 (--generate 인지 --upload 인지)
    mode = sys.argv[1] if len(sys.argv) > 1 else ""

    if mode == "--generate":
        print("--- 이미지 생성 모드 시작 ---")
        if not os.path.exists("images"): os.makedirs("images")
        data = get_processed_news()
        if data:
            create_slides(data)
            # 나중에 업로드 때 쓰기 위해 요약본을 임시 파일로 저장
            with open("summary.txt", "w", encoding="utf-8") as f:
                f.write(data['summary_ko'])
        print("--- 이미지 생성 완료 ---")

    elif mode == "--upload":
        print("--- 인스타그램 업로드 모드 시작 ---")
        # 저장된 요약본 읽기
        if os.path.exists("summary.txt"):
            with open("summary.txt", "r", encoding="utf-8") as f:
                summary_ko = f.read()
            
            image_paths = ["images/slide_0.png", "images/slide_1.png", "images/slide_2.png"]
            
            # 여기서 중요한 점: 이미지가 GitHub에 반영될 시간을 10초만 더 줍니다.
            print("GitHub 반영 대기 중...")
            time.sleep(10)
            
            # 기존 업로드 함수 실행 (article 대신 summary_ko 전달하도록 소폭 수정 필요)
            upload_to_insta(image_paths, summary_ko)
        print("--- 업로드 프로세스 종료 ---")

# 3. 인스타그램 업로드 (깔끔한 한국어 본문)
def upload_to_insta(image_paths, article):
    access_token = os.getenv('INSTA_ACCESS_TOKEN')
    account_id = os.getenv('INSTA_USER_ID')
    user_name = "bomhi"
    repo_name = "insta-automation"
    
    container_ids = []
    for path in image_paths:
        img_url = f"https://raw.githubusercontent.com/{user_name}/{repo_name}/main/{path}"
        res = requests.post(f"https://graph.facebook.com/v19.0/{account_id}/media", data={
            'image_url': img_url, 'is_carousel_item': 'true', 'access_token': access_token
        }).json()
        if 'id' in res: container_ids.append(res['id'])
        time.sleep(5)

    # 본문: 요청하신 대로 번역 요약본만 깔끔하게!
    caption = f"🌍 오늘의 글로벌 핵심 뉴스\n\n{article['summary_ko']}\n\n#뉴스 #해외뉴스 #세계뉴스 #번역뉴스 #자동화"

    carousel_res = requests.post(f"https://graph.facebook.com/v19.0/{account_id}/media", data={
        'media_type': 'CAROUSEL',
        'children': ','.join(container_ids),
        'caption': caption,
        'access_token': access_token
    }).json()
    
    if 'id' in carousel_res:
        print("최종 게시 승인 대기 중...")
        time.sleep(30)
        requests.post(f"https://graph.facebook.com/v19.0/{account_id}/media_publish", data={
            'creation_id': carousel_res['id'], 'access_token': access_token
        })
        print("✅ 게시 완료!")

if __name__ == "__main__":
    if not os.path.exists("images"): os.makedirs("images")
    data = get_processed_news()
    if data:
        paths = create_slides(data)
        upload_to_insta(paths, data)
