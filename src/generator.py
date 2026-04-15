import os
import requests
import time
import sys
import textwrap
import random
import re
import shutil
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
from deep_translator import GoogleTranslator
from bs4 import BeautifulSoup

# [설정]
INSTA_ID = "@world_folio"
# 제외할 유해 단어
SOFT_BLACKLIST = ['death', 'violence', 'murder', 'blood']
# 사진 설명 제외용 키워드
SKIP_KEYWORDS = ['AP Photo', 'AP 사진', 'Photo/', 'Photograph', 'Caption', '©', '출처:', '연설하고', '손짓을', '반응하고', '재배포 금지']

def is_valid_paragraph(text):
    text = text.strip()
    if len(text) < 60: return False
    if any(kw in text for kw in SKIP_KEYWORDS): return False
    if text.startswith('(') and text.endswith(')'): return False
    return True

def crawl_full_text(url):
    """기사 URL에서 본문 텍스트를 크롤링하고 정제합니다."""
    headers = {'User-Agent': 'Mozilla/5.0'}
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
    print("\n🔍 [1단계: 뉴스 수집 및 의미 기반 제목 검증]")
    api_key = os.getenv('NEWS_API_KEY')
    url = f"https://newsapi.org/v2/top-headlines?country=us&pageSize=20&apiKey={api_key}"
    
    try:
        data = requests.get(url).json()
        articles = [a for a in data.get('articles', []) if a.get('urlToImage') and a.get('url')]
        
        for a in articles:
            check_text = (a['title'] + (a['description'] or "")).lower()
            if any(word in check_text for word in SOFT_BLACKLIST): continue
            
            print(f"🔗 원문 분석 시도: {a['title'][:30]}...")
            full_text = crawl_full_text(a['url']) or ((a['description'] or "") + " " + (a['content'] or ""))
            full_text = re.sub(r'\[\+\d+ chars\]', '', full_text)

            translator = GoogleTranslator(source='en', target='ko')
            ko_full_text = translator.translate(full_text[:2000])
            source_name = a['source']['name'] or "Global News"
            
            # [제목 간소화 로직 고도화: 의미가 자연스럽게 이어지도록 요약]
            # 1. 언론사 이름 제거 (CNN, AP News 등)
            raw_title = a['title'].split(' - ')[0]
            ko_title = translator.translate(raw_title)

            # 2. 의미 기반 제목 요약: 어절 단위로 자르되, 자연스럽게 "..." 추가
            max_title_len = 32 # 한국어 기준 한글자씩 끊기지 않는 safe limit
            if len(ko_title) > max_title_len:
                # 쉼표나 콜론 등 의미 단위로 먼저 자르기 시도
                first_unit = ko_title.split(',')[0].split(':')[0].strip()
                if len(first_unit) <= max_title_len:
                    ko_title = first_unit + "..."
                else:
                    # 여전히 길면, character 기준으로 어절 경계에서 자름
                    # last_space를 찾아 그 전까지만 사용
                    truncated = first_unit[:max_title_len].strip()
                    last_space = truncated.rfind(' ')
                    if last_space > 0:
                        ko_title = truncated[:last_space].strip() + "..."
                    else:
                        ko_title = truncated + "..." # 공백이 없으면 글자수대로 자름

            # [요약 구성: 8~10줄 스토리텔링형]
            summary = f"📢 [World Folio Briefing: {ko_title}]\n\n"
            # 마침표 기준으로 문장 분리
            sentences = [s.strip() for s in ko_full_text.split('. ') if len(s) > 20]
            final_sentences = []
            for s in sentences:
                if any(kw in s for kw in ['연설하는', '사진/', '제공', '설명하고']): continue
                if s not in final_sentences and len(final_sentences) < 10:
                    final_sentences.append(s)
            
            # 스토리텔링형으로 풀어서 구성
            if len(final_sentences) > 0:
                summary += f"✅ 핵심 이슈입니다. {final_sentences[0]}\n\n"
            if len(final_sentences) > 1:
                summary += f"📝 상세 배경을 살펴보면, {'. '.join(final_sentences[1:5])}.\n\n"
            if len(final_sentences) > 5:
                summary += f"💡 현재 전문가들은 {'. '.join(final_sentences[5:8])} 상황으로 분석하며, 앞으로의 추이가 예의주시됩니다.\n"
            
            if len(final_sentences) < 5: continue

            # 테마 검색 쿼리 강화 (Unsplash)
            search_query = raw_title.split(' ')[0] + " " + raw_title.split(' ')[1]

            print(f"✅ 정제된 리포트 생성 완료 (출처: {source_name})")
            return {
                'ko_title': ko_title, 
                'en_title_short': search_query, # 테마 이미지 검색용
                'summary_ko': summary, 
                'image_url': a.get('urlToImage'), 
                'source_name': source_name
            }
    except Exception as e:
        print(f"❌ 뉴스 수집 실패: {e}")
    return None

def create_slides(article):
    print("\n🎨 [2단계: 슬라이드 테마 제작]")
    width, height = 1080, 1080
    
    # 1. 원본 기사 사진 로드 (Smart Crop용, Slide 2)
    orig_res = requests.get(article['image_url'], stream=True, timeout=10)
    raw_img = Image.open(orig_res.raw).convert('RGB')

    # 2. 테마 이미지 로드 (AI 생성 느낌, Slide 3, Unsplash)
    # 테마 검색 쿼리 강화: concept, abstract, news 등의 키워드 추가
    search_query = article['en_title_short'] + ",news,conflict,peace,agreement,concept"
    theme_url = f"https://source.unsplash.com/featured/1080x1080/?{search_query}"
    
    try:
        theme_res = requests.get(theme_url, stream=True, timeout=10)
        theme_img = Image.open(theme_res.raw).convert('RGB').resize((width, height), Image.Resampling.LANCZOS)
    except:
        # 실패 시 Grayscale로 변형해서라도 다르게 보이게 함
        theme_img = raw_img.copy().resize((width, height), Image.Resampling.LANCZOS).convert('L').convert('RGB')
    
    font_path = "NanumSquareR.ttf"
    try:
        title_font = ImageFont.truetype(font_path, 80)
        id_font = ImageFont.truetype(font_path, 28)
        source_font = ImageFont.truetype(font_path, 22)
    except:
        title_font = id_font = source_font = ImageFont.load_default()

    # --- 슬라이드 1: 타이틀 (Slide 2 블러 + 제목) ---
    # 사용자 요청: 적당한 블러 (radius=15), 전체 배경 블러.
    s1 = raw_img.copy().resize((width, height), Image.Resampling.LANCZOS)
    s1 = s1.filter(ImageFilter.GaussianBlur(radius=15)) # 옅게 수정
    s1 = ImageEnhance.Brightness(s1).enhance(0.4) # 가독성
    draw = ImageDraw.Draw(s1)
    # 우측 상단 ID
    draw.text((width - 60, 60), INSTA_ID, fill=(255, 255, 255, 180), font=id_font, anchor="ra")
    # 중앙 제목 (의미 기반 요약 버전)
    wrapped_title = textwrap.fill(article['ko_title'], width=12)
    draw.multiline_text((width//2, height//2), wrapped_title, fill=(255, 255, 255), font=title_font, anchor="mm", align="center", spacing=30)
    # 우측 하단 출처
    draw.text((width - 60, height - 60), f"Source: {article['source_name']}", fill=(255, 255, 255, 120), font=source_font, anchor="rd")
    s1.save("images/slide_0.png")

    # --- 슬라이드 2: 원본 기사 사진 (1:1 스마트 크롭) ---
    # 레터박스 대신 피드에 꽉 차게 중앙 크롭
    img_w, img_h = raw_img.size
    min_dim = min(img_w, img_h)
    # 중앙을 기준으로 정사각형으로 자르기
    left = (img_w - min_dim) / 2
    top = (img_h - min_dim) / 2
    s2 = raw_img.crop((left, top, left + min_dim, top + min_dim))
    s2 = s2.resize((width, height), Image.Resampling.LANCZOS)
    s2.save("images/slide_1.png")

    # --- 슬라이드 3: 테마 이미지 (생성 이미지 역할) ---
    # 뉴스 분석 전망을 기반으로 한 컨셉 이미지 배치
    theme_img.save("images/slide_2.png")
    
    return ["images/slide_0.png", "images/slide_1.png", "images/slide_2.png"]

def upload_to_insta(summary_ko):
    print("\n📤 [3단계: 인스타그램 최종 게시]")
    access_token = os.getenv('INSTA_ACCESS_TOKEN')
    account_id = os.getenv('INSTA_USER_ID')
    user_name = "bomhi"
    repo_name = "insta-automation"
    
    container_ids = []
    # 3장 업로드 루프
    for i in range(3):
        img_url = f"https://raw.githubusercontent.com/{user_name}/{repo_name}/main/images/slide_{i}.png?t={int(time.time())}"
        res = requests.post(f"https://graph.facebook.com/v19.0/{account_id}/media", data={
            'image_url': img_url, 'is_carousel_item': 'true', 'access_token': access_token
        }).json()
        if 'id' in res: container_ids.append(res['id'])
        time.sleep(10)

    carousel_res = requests.post(f"https://graph.facebook.com/v19.0/{account_id}/media", data={
        'media_type': 'CAROUSEL', 'children': ','.join(container_ids),
        'caption': summary_ko + "\n\n#news #insight #world_folio", 'access_token': access_token
    }).json()
    
    if 'id' in carousel_res:
        time.sleep(60)
        requests.post(f"https://graph.facebook.com/v19.0/{account_id}/media_publish", data={'creation_id': carousel_res['id'], 'access_token': access_token})
        print("🎉 인스타그램 게시 완료!")

def main():
    if len(sys.argv) < 2: return
    mode = sys.argv[1]

    if mode == "--generate":
        # 폴더 및 요약 파일 자동 삭제
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
        else:
            print("❌ 요약 파일이 없습니다.")

if __name__ == "__main__":
    main()
