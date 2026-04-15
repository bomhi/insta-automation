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
from bs4 import BeautifulSoup # 크롤링을 위한 라이브러리

# [설정]
INSTA_ID = "@world_folio"
SOFT_BLACKLIST = ['brutal', 'mutilated', 'disturbing', 'graphic', 'gore', 'suicide']

def crawl_full_text(url):
    """기사 URL에서 본문 텍스트를 크롤링합니다."""
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    try:
        res = requests.get(url, headers=headers, timeout=10)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # 일반적인 뉴스 사이트의 본문이 들어있는 <p> 태그들을 수집
        paragraphs = soup.find_all('p')
        content = " ".join([p.get_text().strip() for p in paragraphs if len(p.get_text()) > 40])
        
        # 너무 긴 경우 번역 제한을 위해 앞부분 2500자만 사용
        return content[:2500] if len(content) > 100 else None
    except Exception as e:
        print(f"⚠️ 크롤링 실패 ({url}): {e}")
        return None

def get_processed_news():
    print("\n🔍 [1단계: 뉴스 수집 및 본문 크롤링 시작]")
    api_key = os.getenv('NEWS_API_KEY')
    url = f"https://newsapi.org/v2/top-headlines?country=us&pageSize=15&apiKey={api_key}"
    
    try:
        data = requests.get(url).json()
        articles = [a for a in data.get('articles', []) if a.get('urlToImage') and a.get('url')]
        
        for a in articles:
            # 검증
            check_text = (a['title'] + (a['description'] or "")).lower()
            if any(word in check_text for word in SOFT_BLACKLIST): continue
            
            print(f"🔗 원문 크롤링 시도 중: {a['title'][:30]}...")
            full_text = crawl_full_text(a['url'])
            
            # 크롤링 실패 시 NewsAPI의 기본 content 사용 (백업)
            if not full_text:
                print("💡 크롤링 결과가 부족하여 기본 데이터를 사용합니다.")
                full_text = (a['description'] or "") + " " + (a['content'] or "")

            # 특수 기호 및 노이즈 제거
            full_text = re.sub(r'\[\+\d+ chars\]', '', full_text)
            
            # 번역 (내용이 길면 나누어서 번역하거나 핵심만 번역)
            translator = GoogleTranslator(source='en', target='ko')
            ko_title = translator.translate(a['title'])
            
            # 본문 번역 (너무 길면 에러날 수 있으므로 1500자 정도로 끊음)
            ko_full_text = translator.translate(full_text[:1500])
            source_name = a['source']['name'] or "Global News"
            
            # [8~10줄 분량의 유연한 요약 로직]
            summary = f"📍 {ko_title}\n\n"
            # 문장 분리 (마침표 기준)
            raw_sentences = [s.strip() for s in ko_full_text.split('. ') if len(s) > 15]
            
            # 중복 및 유사 문장 필터링하며 8~10문장 선정
            final_sentences = []
            for s in raw_sentences:
                if s not in final_sentences and len(final_sentences) < 9:
                    # 너무 긴 문장은 적당히 자르거나 정제
                    clean_s = s.replace('\n', ' ').strip()
                    final_sentences.append(clean_s)
            
            for s in final_sentences:
                summary += f"• {s}.\n"
            
            # 분량이 모자랄 경우를 대비한 문구 추가
            if len(final_sentences) < 6:
                summary += f"\n👉 현재 {source_name}을 포함한 주요 외신에서 해당 이슈를 비중 있게 다루고 있으며, 추가적인 분석 결과가 나오는 대로 업데이트될 예정입니다."

            print(f"✅ 기사 요약 완료 (분량: {len(final_sentences) + 2}줄)")
            return {
                'ko_title': ko_title, 
                'summary_ko': summary, 
                'image_url': a.get('urlToImage'),
                'source_name': source_name
            }
    except Exception as e:
        print(f"❌ 뉴스 수집 중 치명적 오류: {e}")
    return None

# ... [create_slides, upload_to_insta 함수는 기존과 동일하게 유지] ...

def create_slides(article):
    # (이전 코드와 동일: 슬라이드 1은 시각화, 슬라이드 2는 원본 사진)
    # 생략된 부분은 이전 마스터 버전을 그대로 사용하세요.
    pass

def main():
    if len(sys.argv) < 2: return
    mode = sys.argv[1]

    if mode == "--generate":
        # 1. 기존 이미지 폴더 청소
        if os.path.exists("images"):
            print("🧹 기존 이미지 폴더를 비웁니다...")
            shutil.rmtree("images")
        os.makedirs("images")
        
        # 2. 기존 요약 파일(summary.txt) 삭제 (요청하신 기능!)
        if os.path.exists("summary.txt"):
            print("📄 기존 요약 파일을 삭제합니다...")
            os.remove("summary.txt")
        
        # 3. 새로운 뉴스 데이터 생성
        data = get_processed_news()
        if data:
            create_slides(data)
            with open("summary.txt", "w", encoding="utf-8") as f:
                f.write(data['summary_ko'])
            print("\n✅ 모든 예전 데이터를 지우고 고품질 새 콘텐츠를 준비했습니다!")

    elif mode == "--upload":
        # (이전 업로드 로직과 동일)
        pass

if __name__ == "__main__":
    main()
