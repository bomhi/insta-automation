import os
import requests
import time
import sys
import textwrap
import random
import re
import shutil
from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
from deep_translator import GoogleTranslator
from bs4 import BeautifulSoup

# [설정]
INSTA_ID = "@world_folio"
SKIP_KEYWORDS = ['AP Photo', 'AP 사진', 'Photo/', 'Photograph', 'Caption', '©', '출처:', '연설하고', '손짓을', '기다리는', '반응하고', '재배포 금지']

def is_valid_paragraph(text):
    """사진 설명이나 저작권 정보인지 검사합니다."""
    text = text.strip()
    if len(text) < 60: return False
    if any(kw in text for kw in SKIP_KEYWORDS): return False
    if text.startswith('(') and text.endswith(')'): return False
    return True

def crawl_full_text(url):
    """기사 URL에서 본문 텍스트를 크롤링하고 정제합니다."""
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    try:
        res = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        paragraphs = soup.find_all('p')
        valid_paragraphs = [p.get_text().strip() for p in paragraphs if is_valid_paragraph(p.get_text())]
        content = " ".join(valid_paragraphs)
        return content[:3000] if len(content) > 100 else None
    except:
        return None

def get_processed_news():
    print("\n🔍 [1단계: 뉴스 수집 및 크롤링]")
    api_key = os.getenv('NEWS_API_KEY')
    url = f"https://newsapi.org/v2/top-headlines?country=us&pageSize=20&apiKey={api_key}"
    
    try:
        data = requests.get(url).json()
        articles = [a for a in data.get('articles', []) if a.get('urlToImage') and a.get('url')]
        
        for a in articles:
            check_text = (a['title'] + (a['description'] or "")).lower()
            if any(word in check_text for word in ['death', 'violence', 'murder', 'blood']): continue
            
            print(f"🔗 본문 분석 시도: {a['title'][:30]}...")
            full_text = crawl_full_text(a['url']) or ((a['description'] or "") + " " + (a['content'] or ""))
            full_text = re.sub(r'\[\+\d+ chars\]', '', full_text)

            translator = GoogleTranslator(source='en', target='ko')
            ko_title = translator.translate(a['title'])
            ko_full_text = translator.translate(full_text[:2000])
            source_name = a['source']['name'] or "Global News"
            
            summary = f"📍 {ko_title}\n\n"
            sentences = [s.strip() for s in ko_full_text.split('. ') if len(s) > 20]
            final_sentences = []
            for s in sentences:
                if any(kw in s for kw in ['연설하는', '사진/', '제공', '설명하고']): continue
                if s not in final_sentences and len(final_sentences) < 10:
                    final_sentences.append(s)
            
            for s in final_sentences:
                summary += f"• {s}.\n"
            
            if len(final_sentences) < 5: continue

            return {'ko_title': ko_title, 'summary_ko': summary, 'image_url': a.get('urlToImage'), 'source_name': source_name}
    except Exception as e:
        print(f"❌ 뉴스 수집 중 오류: {e}")
    return None

def create_slides(article):
    print("\n🎨 [2단계: 이미지 생성]")
    width, height = 1080, 1080
    res = requests.get(article['image_url'], stream=True, timeout=10)
    raw_img = Image.open(res.raw).convert('RGB')

    font_path = "NanumSquareR.ttf"
    try:
        title_font = ImageFont.truetype(font_path, 72)
        id_font = ImageFont.truetype(font_path, 26)
        source_font = ImageFont.truetype(font_path, 20)
    except:
        title_font = id_font = source_font = ImageFont.load_default()

    # 슬라이드 0 (타이틀)
    s1 = raw_img.copy().resize((width, height), Image.Resampling.LANCZOS).filter(ImageFilter.GaussianBlur(radius=35))
    s1 = ImageEnhance.Brightness(s1).enhance(0.25)
    draw = ImageDraw.Draw(s1)
    draw.text((width - 60, 60), INSTA_ID, fill=(255, 255, 255, 120), font=id_font, anchor="ra")
    wrapped_title = textwrap.fill(article['ko_title'], width=14)
    draw.multiline_text((width//2, height//2), wrapped_title, fill=(255, 255, 255), font=title_font, anchor="mm", align="center", spacing=25)
    draw.text((width - 50, height - 50), f"출처: {article['source_name']}", fill=(255, 255, 255, 90), font=source_font, anchor="rd")
    s1.save("images/slide_0.png")

    # 슬라이드 1 (메인 사진)
    s2_orig = raw_img.copy()
    s2_orig.thumbnail((width - 100, height - 100), Image.Resampling.LANCZOS)
    s2 = Image.new('RGB', (width, height), color=(15, 15, 15))
    s2.paste(s2_orig, ((width - s2_orig.size[0]) // 2, (height - s2_orig.size[1]) // 2))
    s2.save("images/slide_1.png")
    return ["images/slide_0.png", "images/slide_1.png"]

def upload_to_insta(summary_ko):
    print("\n📤 [3단계: 인스타그램 업로드]")
    access_token = os.getenv('INSTA_ACCESS_TOKEN')
    account_id = os.getenv('INSTA_USER_ID')
    user_name = "bomhi"
    repo_name = "insta-automation"
    
    container_ids = []
    for i in range(2):
        img_url = f"https://raw.githubusercontent.com/{user_name}/{repo_name}/main/images/slide_{i}.png?t={int(time.time())}"
        res = requests.post(f"https://graph.facebook.com/v19.0/{account_id}/media", data={
            'image_url': img_url, 'is_carousel_item': 'true', 'access_token': access_token
        }).json()
        if 'id' in res: container_ids.append(res['id'])
        time.sleep(10)

    carousel_res = requests.post(f"https://graph.facebook.com/v19.0/{account_id}/media", data={
        'media_type': 'CAROUSEL', 'children': ','.join(container_ids),
        'caption': f"🌍 오늘의 글로벌 핵심 브리핑\n\n{summary_ko}\n\n#뉴스 #세계뉴스 #world_folio", 'access_token': access_token
    }).json()
    
    if 'id' in carousel_res:
        time.sleep(60)
        requests.post(f"https://graph.facebook.com/v19.0/{account_id}/media_publish", data={'creation_id': carousel_res['id'], 'access_token': access_token})
        print("🎉 업로드 완료!")

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
            print("🚀 생성 완료!")
    
    elif mode == "--upload":
        if os.path.exists("summary.txt"):
            with open("summary.txt", "r", encoding="utf-8") as f:
                summary = f.read()
            upload_to_insta(summary)
        else:
            print("❌ 요약 파일이 없습니다.")

if __name__ == "__main__":
    main()
