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
# 광고성 및 불필요한 뉴스레터 문구 필터링
JUNK_PHRASES = ['가입', '뉴스레터', '이메일', '구독', 'Copyright', 'All rights reserved', 'Insider', '알림을 받게', '클릭하면']
SKIP_KEYWORDS = ['AP Photo', 'AP 사진', 'Photo/', 'Photograph', 'Caption', '©', '출처:', '연설하고', '손짓을', '재배포 금지']

def is_valid_paragraph(text):
    text = text.strip()
    if len(text) < 60: return False
    if any(junk in text for junk in JUNK_PHRASES): return False
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
    print("\n🔍 [1단계: 뉴스 수집 및 고도화된 요약 분석]")
    api_key = os.getenv('NEWS_API_KEY')
    url = f"https://newsapi.org/v2/top-headlines?country=us&pageSize=15&apiKey={api_key}"
    
    try:
        data = requests.get(url).json()
        articles = [a for a in data.get('articles', []) if a.get('urlToImage') and a.get('url')]
        
        for a in articles:
            full_text = crawl_full_text(a['url'])
            if not full_text or len(full_text) < 400: continue

            translator = GoogleTranslator(source='en', target='ko')
            
            # [제목 요약: 의미가 통하도록 자연스럽게 요약]
            en_title = a['title'].split(' - ')[0]
            ko_title = translator.translate(en_title)
            
            # 제목이 너무 길면 핵심 의미 단위(쉼표, 콜론 등)로 먼저 끊어 가독성 확보
            if len(ko_title) > 32:
                short_title = ko_title.split(',')[0].split(':')[0].strip()
                if len(short_title) > 30:
                    # 어절 단위로 안전하게 자르기
                    words = short_title.split(' ')
                    ko_title = ""
                    for word in words:
                        if len(ko_title + word) < 28:
                            ko_title += word + " "
                        else: break
                    ko_title = ko_title.strip() + "..."
                else:
                    ko_title = short_title

            ko_full_text = translator.translate(full_text[:2500])
            source_name = a['source']['name'] or "Global News"
            sentences = [s.strip() for s in ko_full_text.split('. ') if len(s) > 25]
            
            if len(sentences) < 6: continue

            # [장문 매거진 스타일 요약]
            summary = f"📢 [{ko_title}]\n\n"
            summary += f"✅ 핵심 이슈: {sentences[0]}.\n\n"
            summary += f"📝 배경 설명: {'. '.join(sentences[1:5])}.\n\n"
            summary += f"💡 분석 전망: {'. '.join(sentences[5:8])} 상황으로 분석되며 향후 추이가 주목됩니다.\n\n"
            summary += "간단히 보기"

            # 3번 슬라이드 이미지 검색어 (주제어 추출)
            search_query = en_title.split(' ')[0] + " " + en_title.split(' ')[1]

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
    print("\n🎨 [2단계: 슬라이드 3장 제작]")
    width, height = 1080, 1080
    
    # 원본 기사 사진 로드
    orig_res = requests.get(article['image_url'], stream=True, timeout=10)
    raw_img = Image.open(orig_res.raw).convert('RGB')

    # [3번 슬라이드용 주제별 컨셉 이미지]
    theme_url = f"https://source.unsplash.com/featured/1080x1080/?{article['en_title_short']},concept,abstract,futuristic"
    try:
        theme_res = requests.get(theme_url, stream=True, timeout=10)
        theme_img = Image.open(theme_res.raw).convert('RGB').resize((width, height), Image.Resampling.LANCZOS)
    except:
        theme_img = raw_img.copy().resize((width, height), Image.Resampling.LANCZOS).filter(ImageFilter.EDGE_ENHANCE)

    font_path = "NanumSquareR.ttf"
    try:
        title_font = ImageFont.truetype(font_path, 80)
        id_font = ImageFont.truetype(font_path, 30)
        source_font = ImageFont.truetype(font_path, 24)
    except:
        title_font = id_font = source_font = ImageFont.load_default()

    # --- 1번 장: 타이틀 (원본 사진 연한 블러 + 제목) ---
    s1 = raw_img.copy().resize((width, height), Image.Resampling.LANCZOS).filter(ImageFilter.GaussianBlur(radius=10))
    s1 = ImageEnhance.Brightness(s1).enhance(0.4)
    draw = ImageDraw.Draw(s1)
    draw.text((width - 60, 60), INSTA_ID, fill=(255, 255, 255, 180), font=id_font, anchor="ra")
    wrapped_title = textwrap.fill(article['ko_title'], width=12)
    draw.multiline_text((width//2, height//2), wrapped_title, fill=(255, 255, 255), font=title_font, anchor="mm", align="center", spacing=30)
    draw.text((width - 60, height - 60), f"Source: {article['source_name']}", fill=(255, 255, 255, 120), font=source_font, anchor="rd")
    s1.save("images/slide_0.png")

    # --- 2번 장: 기사 원본 사진 (레터박스) ---
    s2_orig = raw_img.copy()
    s2_orig.thumbnail((width - 120, height - 120), Image.Resampling.LANCZOS)
    s2 = Image.new('RGB', (width, height), color=(15, 15, 15))
    s2.paste(s2_orig, ((width - s2_orig.size[0]) // 2, (height - s2_orig.size[1]) // 2))
    s2.save("images/slide_1.png")

    # --- 3번 장: 주제 부합 컨셉 이미지 (새로운 사진) ---
    theme_img.save("images/slide_2.png")
    
    return ["images/slide_0.png", "images/slide_1.png", "images/slide_2.png"]

def upload_to_insta(summary_ko):
    print("\n📤 [3단계: 인스타그램 최종 게시]")
    access_token = os.getenv('INSTA_ACCESS_TOKEN')
    account_id = os.getenv('INSTA_USER_ID')
    user_name = "bomhi" # 사용자님의 GitHub ID
    repo_name = "insta-automation" # 사용자님의 저장소 이름
    
    container_ids = []
    # 3장 업로드 루프
    for i in range(3):
        img_url = f"https://raw.githubusercontent.com/{user_name}/{repo_name}/main/images/slide_{i}.png?t={int(time.time())}"
        # 아래 줄이 오류가 났던 부분입니다. 따옴표와 괄호를 정확히 닫았습니다.
        res = requests.post(f"https://graph.facebook.com/v19.0/{account_id}/media", data={
            'image_url': img_url, 
            'is_carousel_item': 'true', 
            'access_token': access_token
        }).json()
        
        if 'id' in res:
            container_ids.append(res['id'])
            print(f"✅ 슬라이드 {i} 컨테이너 생성 성공")
        else:
            print(f"❌ 슬라이드 {i} 생성 실패: {res}")
        time.sleep(10)

    # 슬라이드 합치기 (Carousel 생성)
    carousel_res = requests.post(f"https://graph.facebook.com/v19.0/{account_id}/media", data={
        'media_type': 'CAROUSEL', 
        'children': ','.join(container_ids),
        'caption': summary_ko + "\n\n#news #global #insight #world_folio", 
        'access_token': access_token
    }).json()
    
    if 'id' in carousel_res:
        print("⏳ 게시물 최종 승인 대기 중 (60초)...")
        time.sleep(60)
        requests.post(f"https://graph.facebook.com/v19.0/{account_id}/media_publish", data={
            'creation_id': carousel_res['id'], 
            'access_token': access_token
        })
        print("🎉 인스타그램 업로드 완료!")
    else:
        print(f"❌ 최종 게시 실패: {carousel_res}")

def main():
    if len(sys.argv) < 2: return
    mode = sys.argv[1]

    if mode == "--generate":
        # 이미지 폴더 및 요약 파일 초기화
        if os.path.exists("images"):
            shutil.rmtree("images", ignore_errors=True)
        os.makedirs("images", exist_ok=True)
        
        if os.path.exists("summary.txt"):
            os.remove("summary.txt")
        
        data = get_processed_news()
        if data:
            create_slides(data)
            with open("summary.txt", "w", encoding="utf-8") as f:
                f.write(data['summary_ko'])
            print("🚀 모든 콘텐츠가 성공적으로 생성되었습니다!")
        else:
            print("❌ 적절한 뉴스를 찾지 못했습니다.")
    
    elif mode == "--upload":
        if os.path.exists("summary.txt"):
            with open("summary.txt", "r", encoding="utf-8") as f:
                summary = f.read()
            upload_to_insta(summary)
        else:
            print("❌ 요약 파일(summary.txt)이 없습니다. 먼저 generate를 실행하세요.")

if __name__ == "__main__":
    main()
