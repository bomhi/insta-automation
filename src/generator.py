import os
import requests
import time
import sys
from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
from deep_translator import GoogleTranslator

# [설정]
BLACKLIST = ['death', 'killed', 'murder', 'blood', 'suicide', 'war', 'violence']

def get_processed_news():
    print("📰 뉴스 수집을 시작합니다...")
    api_key = os.getenv('NEWS_API_KEY')
    if not api_key:
        print("❌ NEWS_API_KEY가 설정되지 않았습니다.")
        return None
        
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    url = f"https://newsapi.org/v2/everything?q=world&language=en&from={yesterday}&sortBy=popularity&pageSize=10&apiKey={api_key}"
    
    try:
        data = requests.get(url).json()
        articles = data.get('articles', [])
        for a in articles:
            check_text = (a['title'] + (a['description'] or "")).lower()
            if any(word in check_text for word in BLACKLIST): continue
            
            print(f"✅ 기사 선정: {a['title']}")
            translator = GoogleTranslator(source='en', target='ko')
            ko_title = translator.translate(a['title'])
            ko_desc = translator.translate(a['description'] or "내용 없음")
            
            summary = f"📍 {ko_title}\n\n"
            for s in ko_desc.split('. ')[:4]:
                if len(s) > 5: summary += f"• {s.strip()}\n"
            
            return {'ko_title': ko_title, 'summary_ko': summary, 'image_url': a.get('urlToImage')}
    except Exception as e:
        print(f"❌ 뉴스 수집 중 오류: {e}")
    return None

def create_slides(article):
    print("🎨 이미지 생성을 시작합니다...")
    width, height = 1080, 1080
    try:
        raw_img = Image.open(requests.get(article['image_url'], stream=True).raw).convert('RGB')
    except:
        raw_img = Image.new('RGB', (width, height), color=(30, 30, 30))

    for i in range(3):
        slide = raw_img.copy().resize((width, height), Image.Resampling.LANCZOS)
        if i == 0:
            slide = slide.filter(ImageFilter.GaussianBlur(radius=15))
            slide = ImageEnhance.Brightness(slide).enhance(0.5)
            draw = ImageDraw.Draw(slide)
            try:
                font = ImageFont.truetype("NanumSquareR.ttf", 80)
            except:
                font = ImageFont.load_default()
            
            text = article['ko_title']
            wrapped = "".join([text[j:j+12] + "\n" for j in range(0, len(text), 12)])
            draw.text((width//2, height//2), wrapped.strip(), fill=(255,255,255), font=font, anchor="mm", align="center")
        
        slide.save(f"images/slide_{i}.png")
    print("✅ 이미지 3장 생성 완료")

def upload_to_insta(summary_ko):
    print("📤 인스타그램 업로드를 시작합니다...")
    access_token = os.getenv('INSTA_ACCESS_TOKEN')
    account_id = os.getenv('INSTA_USER_ID')
    
    # 내 아이디로 수정 필수!
    user_name = "bomhi" 
    repo_name = "insta-automation"
    
    container_ids = []
    for i in range(3):
        img_url = f"https://raw.githubusercontent.com/{user_name}/{repo_name}/main/images/slide_{i}.png"
        print(f"이미지 전송 중 ({i+1}/3): {img_url}")
        res = requests.post(f"https://graph.facebook.com/v19.0/{account_id}/media", data={
            'image_url': img_url, 'is_carousel_item': 'true', 'access_token': access_token
        }).json()
        
        if 'id' in res:
            container_ids.append(res['id'])
        else:
            print(f"❌ 컨테이너 생성 실패: {res}")
            return
        time.sleep(10)

    caption = f"🌍 오늘의 글로벌 핵심 브리핑\n\n{summary_ko}\n\n#뉴스 #세계뉴스 #해외뉴스 #world_folio"
    
    print("🔗 캐러셀로 묶는 중...")
    carousel_res = requests.post(f"https://graph.facebook.com/v19.0/{account_id}/media", data={
        'media_type': 'CAROUSEL', 'children': ','.join(container_ids),
        'caption': caption, 'access_token': access_token
    }).json()
    
    if 'id' in carousel_res:
        print("⌛ 인스타 서버 처리 대기 (60초)...")
        time.sleep(60)
        final = requests.post(f"https://graph.facebook.com/v19.0/{account_id}/media_publish", data={
            'creation_id': carousel_res['id'], 'access_token': access_token
        }).json()
        print(f"✅ 최종 결과: {final}")
    else:
        print(f"❌ 캐러셀 생성 실패: {carousel_res}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("❌ 인자가 없습니다. (--generate 또는 --upload)")
        sys.exit(1)

    mode = sys.argv[1]
    if mode == "--generate":
        if not os.path.exists("images"): os.makedirs("images")
        data = get_processed_news()
        if data:
            create_slides(data)
            with open("summary.txt", "w", encoding="utf-8") as f:
                f.write(data['summary_ko'])
    elif mode == "--upload":
        if os.path.exists("summary.txt"):
            with open("summary.txt", "r", encoding="utf-8") as f:
                summary = f.read()
            upload_to_insta(summary)
        else:
            print("❌ summary.txt 파일이 없어 업로드를 중단합니다.")
