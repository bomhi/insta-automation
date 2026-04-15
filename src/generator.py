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
# 뉴스에서 제외할 단어들 (사진 설명, 저작권 관련)
SKIP_KEYWORDS = ['AP Photo', 'AP 사진', 'Photo/', 'Photograph', 'Caption', '©', '출처:', '연설하고', '손짓을', '기다리는', '반응하고', '재배포 금지']

def is_valid_paragraph(text):
    """사진 설명이나 저작권 정보인지 검사합니다."""
    text = text.strip()
    if len(text) < 60: return False # 너무 짧은 문장은 기사 내용이 아닐 확률이 높음
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
        
        valid_paragraphs = []
        for p in paragraphs:
            txt = p.get_text().strip()
            if is_valid_paragraph(txt):
                # 불필요한 접두어 제거 (예: 지역명 (AP) --- )
                txt = re.sub(r'^[^-]*\(AP\) — ', '', txt)
                txt = re.sub(r'^[^-]*— ', '', txt)
                valid_paragraphs.append(txt)
        
        content = " ".join(valid_paragraphs)
        return content[:3000] if len(content) > 100 else None
    except:
        return None

def get_processed_news():
    print("\n🔍 [1단계: 뉴스 수집 및 고품질 크롤링]")
    api_key = os.getenv('NEWS_API_KEY')
    url = f"https://newsapi.org/v2/top-headlines?country=us&pageSize=20&apiKey={api_key}"
    
    try:
        data = requests.get(url).json()
        articles = [a for a in data.get('articles', []) if a.get('urlToImage') and a.get('url')]
        
        for a in articles:
            # 기본 검증
            check_text = (a['title'] + (a['description'] or "")).lower()
            if any(word in check_text for word in ['death', 'violence', 'murder', 'blood']): continue
            
            print(f"🔗 원문 분석 시도: {a['title'][:30]}...")
            full_text = crawl_full_text(a['url'])
            
            # 크롤링 실패 시 기본 데이터 활용
            if not full_text:
                full_text = (a['description'] or "") + " " + (a['content'] or "")
                full_text = re.sub(r'\[\+\d+ chars\]', '', full_text)

            translator = GoogleTranslator(source='en', target='ko')
            ko_title = translator.translate(a['title'])
            
            # 번역 (내용이 너무 길면 끊어서 번역)
            ko_full_text = translator.translate(full_text[:2000])
            source_name = a['source']['name'] or "Global News"
            
            # [요약 구성: 8~12줄 목표]
            summary = f"📍 {ko_title}\n\n"
            sentences = [s.strip() for s in ko_full_text.split('. ') if len(s) > 20]
            
            final_sentences = []
            for s in sentences:
                # 번역된 결과에서도 사진 설명 묘사체 제거
                if any(kw in s for kw in ['연설하는', '사진/', '제공', '설명하고']): continue
                if s not in final_sentences and len(final_sentences) < 10:
                    final_sentences.append(s)
            
            for s in final_sentences:
                summary += f"• {s}.\n"
            
            # 분량이 너무 적으면 다음 기사로 패스
            if len(final_sentences) < 5:
                print("⏩ 내용 부족으로 다음 기사를 찾습니다.")
                continue

            print(f"✅ 정제된 뉴스 리포트 생성 완료 (출처: {source_name})")
            return {
                'ko_title': ko_title, 
                'summary_ko': summary, 
                'image_url': a.get('urlToImage'),
                'source_name': source_name
            }
    except Exception as e:
        print(f"❌ 뉴스 수집 중 오류: {e}")
    return None

def create_slides(article):
    print("\n🎨 [2단계: 이미지 슬라이드 2장 생성]")
    width, height = 1080, 1080
    image_paths = []
    
    try:
        res = requests.get(article['image_url'], stream=True, timeout=10)
        raw_img = Image.open(res.raw).convert('RGB')
    except:
        raw_img = Image.new('RGB', (width, height), color=(30, 30, 30))

    font_path = "NanumSquareR.ttf"
    try:
        title_font = ImageFont.truetype(font_path, 72)
        id_font = ImageFont.truetype(font_path, 26)
        source_font = ImageFont.truetype(font_path, 20)
    except:
        title_font = id_font = source_font = ImageFont.load_default()

    # --- 슬라이드 1: 타이틀 카드 ---
    s1 = raw_img.copy().resize((width, height), Image.Resampling.LANCZOS)
    s1 = s1.filter(ImageFilter.GaussianBlur(radius=35))
    s1 = ImageEnhance.Brightness(s1).enhance(0.25)
    
    draw = ImageDraw.Draw(s1)
    # 우측 상단 ID
    draw.text((width - 60, 60), INSTA_ID, fill=(255, 255, 255, 120), font=id_font, anchor="ra")
    # 중앙 제목
    wrapped_title = textwrap.fill(article['ko_title'], width=14)
    draw.multiline_text((width//2, height//2), wrapped_title, fill=(255, 255, 255), 
                        font=title_font, anchor="mm", align="center", spacing=25)
    # 우측 하단 출처
    draw.text((width - 50, height - 50), f"출처: {article['source_name']}", fill=(255, 255, 255, 90), font=source_font, anchor="rd")
    
    s1.save("images/slide_0.png", quality=95)
    image_paths.append("images/slide_0.png")

    # --- 슬라이드 2: 메인 사진 (Letterbox) ---
    s2_orig = raw_img.copy()
    s2_orig.thumbnail((width - 100, height - 100), Image.Resampling.LANCZOS)
    s2 = Image.new('RGB', (width, height), color=(15, 15, 15))
    s2.paste(s2_orig, ((width - s2_orig.size[0]) // 2, (height - s2_orig.size[1]) // 2))
    
    s2.save("images/slide_1.png", quality=95)
    image_paths.append("images/slide_1.png")
    
    print("✅ 슬라이드 생성 완료")
    return image_paths

def main():
    if len(sys.argv) < 2: return
    mode = sys.argv[1]

    if mode == "--generate":
        # 안전한 폴더 생성 및 기존 파일 삭제
        if os.path.exists("images"):
            shutil.rmtree("images", ignore_errors=True)
        os.makedirs("images", exist_ok=True)
        
        if os
