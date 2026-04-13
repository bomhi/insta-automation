import os
import requests
import time
import sys
import random
from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
from deep_translator import GoogleTranslator

# 1. 설정 및 필터
CATEGORIES = {
    'positive': ['technology', 'science', 'business'],
    'impact': ['general']
}
SOFT_BLACKLIST = ['brutal', 'mutilated', 'disturbing', 'graphic', 'gore', 'suicide']

# 2. 뉴스 수집 및 번역
def get_processed_news():
    api_key = os.getenv('NEWS_API_KEY')
    
    # 80% 확률로 유익한 뉴스, 20% 확률로 사건/사고 뉴스 선택
    is_impact = random.random() < 0.2
    group = 'impact' if is_impact else 'positive'
    target_cat = 'general' if is_impact else random.choice(CATEGORIES['positive'])
    query = "breaking" if is_impact else ""

    url = f"https://newsapi.org/v2/top-headlines?country=us&category={target_cat}&q={query}&apiKey={api_key}"
    
    try:
        data = requests.get(url).json()
        articles = [a for a in data.get('articles', []) if a.get('urlToImage') and a.get('description')]
        
        selected = None
        for a in articles:
            check_text = (a['title'] + a['description']).lower()
            if any(word in check_text for word in SOFT_BLACKLIST): continue
            selected = a
            break
        
        if not selected: return None

        translator = GoogleTranslator(source='en', target='ko')
        ko_title = translator.translate(selected['title'])
        ko_desc = translator.translate(selected['description'])
        
        # 요약 (본문용)
        summary_ko = f"📍 {ko_title}\n\n"
        for s in ko_desc.split('. ')[:4]:
            if len(s) > 5: summary_ko += f"• {s.strip()}\n"

        return {
            'group': group,
            'ko_title': ko_title,
            'summary_ko': summary_ko,
            'image_url': selected['urlToImage']
        }
    except: return None

# 3. 이미지 생성 (디자인 가변 로직)
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
        
        if i == 0: # 첫 번째 장: 뉴스 성격에 따라 디자인 변경
            # 사건 사고(impact)면 블러 강하게(25), 평소면 15
            blur_radius = 25 if article['group'] == 'impact' else 15
            slide = slide.filter(ImageFilter.GaussianBlur(radius=blur_radius))
            slide = ImageEnhance.Brightness(slide).enhance(0.4)
            
            draw = ImageDraw.Draw(slide)
            try:
                font = ImageFont.truetype("NanumSquareR.ttf", 80)
                font_label = ImageFont.truetype("NanumSquareR.ttf", 45)
            except:
                font = font_label = ImageFont.load_default()
            
            # 사건 사고면 빨간색 + 🚨, 평소면 흰색 + 💡
            title_color = (255, 80, 80) if article['group'] == 'impact' else (255, 255, 255)
            label_text = "🚨 BREAKING NEWS" if article['group'] == 'impact' else "💡 DAILY TECH & BIZ"
            
            draw.text((width//2, 200), label_text, fill=title_color, font=font_label, anchor="mm")
            
            # 제목 줄바꿈
            text = article['ko_title']
            wrapped = "".join([text[j:j+12] + "\n" for j in range(0, len(text), 12)])
            draw.text((width//2, height//2), wrapped.strip(), fill=(255,255,255), font=font, anchor="mm", align="center", spacing=20)
        
        path = f"images/slide_{i}.png"
        slide.save(path)
        image_paths.append(path)
    return image_paths

# 4. 메인 컨트롤러 (Generate/Upload 분리)
def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else ""

    if mode == "--generate":
        if not os.path.exists("images"): os.makedirs("images")
        data = get_processed_news()
        if data:
            create_slides(data)
            with open("summary.txt", "w", encoding="utf-8") as f:
                f.write(data['summary_ko'])
            print(f"[{data['group']}] 이미지 생성 완료")

    elif mode == "--upload":
        if os.path.exists("summary.txt"):
            with open("summary.txt", "r", encoding="utf-8") as f:
                summary_ko = f.read()
            upload_to_insta(["images/slide_0.png", "images/slide_1.png", "images/slide_2.png"], summary_ko)

def upload_to_insta(image_paths, summary_ko):
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
        time.sleep(7)

    caption = f"🌍 오늘의 글로벌 핵심 브리핑\n\n{summary_ko}\n\n#뉴스 #해외뉴스 #자동화 #데일리리포트"
    
    carousel_res = requests.post(f"https://graph.facebook.com/v19.0/{account_id}/media", data={
        'media_type': 'CAROUSEL', 'children': ','.join(container_ids),
        'caption': caption, 'access_token': access_token
    }).json()
    
    if 'id' in carousel_res:
        time.sleep(30)
        requests.post(f"https://graph.facebook.com/v19.0/{account_id}/media_publish", data={
            'creation_id': carousel_res['id'], 'access_token': access_token
        })
        print("✅ 인스타그램 게시 완료!")

if __name__ == "__main__":
    main()
