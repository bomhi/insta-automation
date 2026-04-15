import os
import requests
import time
import sys
import textwrap
import re
import shutil
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
from deep_translator import GoogleTranslator
from bs4 import BeautifulSoup

# [설정]
INSTA_ID = "@world_folio"
SKIP_KEYWORDS = ['AP Photo', 'AP 사진', 'Photo/', 'Photograph', 'Caption', '©', '출처:', '연설하고', '손짓을', '반응하고', '재배포 금지']

def is_valid_paragraph(text):
    text = text.strip()
    if len(text) < 50: return False
    if any(kw in text for kw in SKIP_KEYWORDS): return False
    return True

def crawl_full_text(url):
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        res = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        paragraphs = soup.find_all('p')
        valid_paragraphs = [p.get_text().strip() for p in paragraphs if is_valid_paragraph(p.get_text())]
        return " ".join(valid_paragraphs[:15])
    except:
        return None

def get_processed_news():
    print("\n🔍 [1단계: 뉴스 및 주제 분석]")
    api_key = os.getenv('NEWS_API_KEY')
    url = f"https://newsapi.org/v2/top-headlines?country=us&pageSize=15&apiKey={api_key}"
    
    try:
        data = requests.get(url).json()
        articles = [a for a in data.get('articles', []) if a.get('urlToImage') and a.get('url')]
        
        for a in articles:
            full_text = crawl_full_text(a['url'])
            if not full_text or len(full_text) < 300: continue

            translator = GoogleTranslator(source='en', target='ko')
            
            # 제목 간소화 및 키워드 추출
            en_title = a['title'].split(' - ')[0]
            ko_title = translator.translate(en_title)
            if len(ko_title) > 30: ko_title = ko_title[:28] + "..."
            
            # 주제어 추출 (이미지 검색용)
            search_query = en_title.split(' ')[0] + " " + en_title.split(' ')[1]

            ko_full_text = translator.translate(full_text[:2500])
            source_name = a['source']['name'] or "Global News"
            sentences = [s.strip() for s in ko_full_text.split('. ') if len(s) > 25]
            
            # 스토리텔링 요약 (8-10줄)
            summary = f"📢 [World Folio Briefing: {ko_title}]\n\n"
            summary += f"✅ 핵심 이슈: {sentences[0] if len(sentences)>0 else ''}\n\n"
            summary += f"📝 상세 배경: {'. '.join(sentences[1:5])}.\n\n"
            summary += f"💡 분석 전망: {'. '.join(sentences[5:8])}.\n"

            return {
                'ko_title': ko_title, 
                'en_title_short': search_query, 
                'summary_ko': summary, 
                'image_url': a.get('urlToImage'), 
                'source_name': source_name
            }
    except Exception as e:
        print(f"❌ 뉴스 수집 실패: {e}")
    return None

def create_slides(article):
    print("\n🎨 [2단계: 슬라이드 3장 제작 (레터박스 및 테마 적용)]")
    width, height = 1080, 1080
    
    # 1. 원본 기사 사진 로드
    orig_res = requests.get(article['image_url'], stream=True, timeout=10)
    raw_img = Image.open(orig_res.raw).convert('RGB')

    # 2. 테마 이미지 로드 (Unsplash)
    theme_url = f"https://source.unsplash.com/featured/1080x1080/?{article['en_title_short']},concept,abstract"
    try:
        theme_res = requests.get(theme_url, stream=True, timeout=10)
        theme_img = Image.open(theme_res.raw).convert('RGB').resize((width, height), Image.Resampling.LANCZOS)
    except:
        theme_img = raw_img.copy().resize((width, height), Image.Resampling.LANCZOS)
        theme_img = ImageEnhance.Color(theme_img).enhance(0.2) 

    font_path = "NanumSquareR.ttf"
    try:
        title_font = ImageFont.truetype(font_path, 82)
        id_font = ImageFont.truetype(font_path, 30)
        source_font = ImageFont.truetype(font_path, 24)
    except:
        title_font = id_font = source_font = ImageFont.load_default()

    # --- 슬라이드 1: 타이틀 (기사 원본 블러 8 + 제목) ---
    s1 = raw_img.copy().resize((width, height), Image.Resampling.LANCZOS)
    s1 = s1.filter(ImageFilter.GaussianBlur(radius=8)) # 연한 블러
    s1 = ImageEnhance.Brightness(s1).enhance(0.4) # 가독성
    draw = ImageDraw.Draw(s1)
    draw.text((width - 60, 60), INSTA_ID, fill=(255, 255, 255, 200), font=id_font, anchor="ra")
    wrapped_title = textwrap.fill(article['ko_title'], width=12)
    draw.multiline_text((width//2, height//2), wrapped_title, fill=(255, 255, 255), font=title_font, anchor="mm", align="center", spacing=30)
    draw.text((width - 60, height - 60), f"Source: {article['source_name']}", fill=(255, 255, 255, 140), font=source_font, anchor="rd")
    s1.save("images/slide_0.png")

    # --- 슬라이드 2: 기사 원본 (레터박스 스타일) ---
    # 원본 비율 유지하며 1080x1080 안에 맞춤
    s2_orig = raw_img.copy()
    s2_orig.thumbnail((width - 100, height - 100), Image.Resampling.LANCZOS)
    s2 = Image.new('RGB', (width, height), color=(15, 15, 15)) # 어두운 배경
    s2.paste(s2_orig, ((width - s2_orig.size[0]) // 2, (height - s2_orig.size[1]) // 2))
    s2.save("images/slide_1.png")

    # --- 슬라이드 3: 테마 이미지 (생성된 이미지 느낌) ---
    theme_img.save("images/slide_2.png")
    
    return ["images/slide_0.png", "images/slide_1.png", "images/slide_2.png"]

def upload_to_insta(summary_ko):
    print("\n📤 [3단계: 인스타그램 업로드]")
    access_token = os.getenv('INSTA_ACCESS_TOKEN')
    account_id = os.getenv('INSTA_USER_ID')
    user_name = "bomhi"
    repo_name = "insta-automation"
    
    container_ids = []
    for i in range(3):
        img_url = f"https://raw.githubusercontent.com/{user_name}/{repo_name}/main/images/slide_{i}.png?t={int(time.time())}"
        res = requests.post(f"https://graph.facebook.com/v19.0/{account_id}/media", data={
            'image_url': img_url, 'is_carousel_item': 'true', 'access_token': access_token
        }).json()
        if 'id' in res: container_ids.append(res['id'])
        time.sleep(10)

    carousel_res = requests.post(f"https://graph.facebook.com/v19.0/{account_id}/media", data={
        'media_type': 'CAROUSEL', 'children': ','.join(container_ids),
        'caption': summary_ko + "\n\n#worldfolio #globalnews #insight", 'access_token': access_token
    }).json()
    
    if 'id' in carousel_res:
        time.sleep(60)
        requests.post(f"https://graph.facebook.com/v19.0/{account_id}/media_publish", data={'creation_id': carousel_res['id'], 'access_token': access_token})
        print("🎉 모든 슬라이드 게시 완료!")

def main():
    if len(sys.argv) < 2: return
    mode = sys.argv[1]

    if mode == "--generate":
        if os.path.exists("images"): shutil.rmtree("images", ignore_errors=True)
        os.makedirs("images", exist_ok=True)
        if os.path.exists("summary.txt"): os.remove("summary.txt")
        
        data = get_processed_news()
        if data:
            create_slides(data)
            with open("summary.txt", "w", encoding="utf-8") as f:
                f.write(data['summary_ko'])
            print("🚀 콘텐츠 생성 성공!")

    elif mode == "--upload":
        if os.path.exists("summary.txt"):
            with open("summary.txt", "r", encoding="utf-8") as f:
                summary = f.read()
            upload_to_insta(summary)

if __name__ == "__main__":
    main()
