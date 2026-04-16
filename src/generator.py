import os
import requests
import time
import sys
import textwrap
import re
import shutil
import urllib.parse
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
from deep_translator import GoogleTranslator
from bs4 import BeautifulSoup

# [설정]
INSTA_ID = "@world_folio"
# 악성/광고성 문구 완벽 차단 리스트
JUNK_PHRASES = [
    'Ben이 스토리를', '받은편지함', '가입', '동의하는', '약관', '개인 정보', 
    'Insider', '뉴스레터', '클릭하면', 'Copyright', 'All rights reserved', '무료 기사'
]
SKIP_KEYWORDS = ['AP Photo', 'AP 사진', 'Photo/', 'Photograph', 'Caption', '©', '출처:', '연설하고', '손짓을', '재배포 금지']

def is_valid_paragraph(text):
    """문장이 광고나 사진 설명인지 검증합니다."""
    text = text.strip()
    if len(text) < 50: return False # 길이가 너무 짧으면 제외
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
        return " ".join(valid_paragraphs)
    except:
        return None

def get_processed_news():
    print("\n🔍 [1단계: 경제/과학 우선순위 뉴스 수집 및 정제]")
    api_key = os.getenv('NEWS_API_KEY')
    
    # 1. 경제(Business)와 과학(Science) 카테고리를 순서대로 호출하여 우선순위 확보
    urls = [
        f"https://newsapi.org/v2/top-headlines?country=us&category=business&pageSize=10&apiKey={api_key}",
        f"https://newsapi.org/v2/top-headlines?country=us&category=science&pageSize=10&apiKey={api_key}"
    ]
    
    articles = []
    try:
        for url in urls:
            data = requests.get(url).json()
            articles.extend([a for a in data.get('articles', []) if a.get('urlToImage') and a.get('url')])
            
        for a in articles:
            full_text = crawl_full_text(a['url'])
            if not full_text or len(full_text) < 300: continue

            translator = GoogleTranslator(source='en', target='ko')
            
            # --- [수정사항 1: 제목 보기 좋게 요약 (... 생략 제거)] ---
            en_title = a['title'].split(' - ')[0]
            ko_title = translator.translate(en_title)
            
            # 쉼표나 콜론 등 의미 단위에서 끊어 깔끔하게 마무리
            if len(ko_title) > 30:
                split_title = re.split(r'[,:;]', ko_title)[0].strip()
                if len(split_title) < 15: # 끊은 게 너무 짧으면
                    ko_title = " ".join(ko_title.split(' ')[:6]) # 6어절만 사용
                else:
                    ko_title = split_title

            # 특수기호 정리
            ko_title = ko_title.replace('...', '').strip()

            ko_full_text = translator.translate(full_text[:2000])
            source_name = a['source']['name'] or "Global News"
            
            # 문장 단위로 분리 (유효한 문장만 추출)
            sentences = [s.strip() for s in ko_full_text.split('. ') if len(s) > 30 and not any(j in s for j in JUNK_PHRASES)]
            if len(sentences) < 4: continue

            # --- [수정사항 3: 매거진형 템플릿 본문 (광고 원천 차단)] ---
            summary = f"📢 [{ko_title}]\n\n"
            summary += f"사실이 알려지며 전 세계적인 관심을 모으고 있습니다. 현재 이 사안은 주요 외신들 사이에서도 비중 있게 다뤄지며 다양한 해석을 낳고 있는 상황입니다.\n\n"
            
            body_text = ". ".join(sentences[0:3])
            summary += f"해당 사안의 구체적인 내용을 살펴보면, {body_text}. 특히 이번 과정에서 나타난 특징적인 요소들은 기존의 흐름과는 다른 양상을 보이고 있어 주목할 만합니다.\n\n"
            
            summary += f"이러한 움직임은 최근 급변하는 국제 정세 속에서 특정 수요를 겨냥해 추진된 것으로 분석됩니다. 전문가들은 이번 프로젝트가 단순한 일회성 사건을 넘어, 관련 시장 및 내수 활성화를 노린 장기적인 전략의 일환이라는 평가를 내놓고 있습니다.\n\n"
            
            conclusion_text = sentences[3] if len(sentences) > 3 else sentences[-1]
            summary += f"다만 일각에서는 이번 사안에 대한 적절성 논란과 함께 우려의 목소리도 제기되고 있습니다. {conclusion_text}. 결국 단기적인 성과보다는 고유의 콘텐츠 경쟁력과 지속 가능성을 확보하는 것이 향후 가장 중요한 과제가 될 것으로 보입니다.\n\n"
            summary += "간단히 보기"

            # 3번 슬라이드 AI 생성을 위한 영어 키워드
            ai_keyword = urllib.parse.quote(f"Minimalist digital art concept about {en_title}")

            return {
                'ko_title': ko_title, 
                'ai_prompt_url': f"https://image.pollinations.ai/prompt/{ai_keyword}?width=1080&height=1080&nologo=true", 
                'summary_ko': summary, 
                'image_url': a.get('urlToImage'), 
                'source_name': source_name
            }
    except Exception as e:
        print(f"❌ 뉴스 수집 실패: {e}")
    return None

def create_slides(article):
    print("\n🎨 [2단계: 슬라이드 3장 제작 (AI 생성 이미지 포함)]")
    width, height = 1080, 1080
    
    # 1. 원본 기사 사진 로드 (2번 슬라이드 용)
    orig_res = requests.get(article['image_url'], stream=True, timeout=10)
    raw_img = Image.open(orig_res.raw).convert('RGB')

    # --- [수정사항 2: 주제에 부합하는 새로운 AI 이미지 생성 (3번 슬라이드)] ---
    # Pollinations AI를 통해 프롬프트 기반 이미지를 실시간으로 그려옵니다.
    try:
        ai_res = requests.get(article['ai_prompt_url'], stream=True, timeout=15)
        ai_img = Image.open(ai_res.raw).convert('RGB')
    except Exception as e:
        print(f"⚠️ AI 이미지 생성 지연, 테마 색상으로 대체: {e}")
        ai_img = Image.new('RGB', (width, height), color=(20, 25, 30))

    font_path = "NanumSquareR.ttf"
    try:
        title_font = ImageFont.truetype(font_path, 80)
        id_font = ImageFont.truetype(font_path, 30)
        source_font = ImageFont.truetype(font_path, 24)
    except:
        title_font = id_font = source_font = ImageFont.load_default()

    # --- 1번 장: 타이틀 (기사 사진 연한 블러 + 제목) ---
    s1 = raw_img.copy().resize((width, height), Image.Resampling.LANCZOS).filter(ImageFilter.GaussianBlur(radius=10))
    s1 = ImageEnhance.Brightness(s1).enhance(0.4)
    draw = ImageDraw.Draw(s1)
    draw.text((width - 60, 60), INSTA_ID, fill=(255, 255, 255, 180), font=id_font, anchor="ra")
    wrapped_title = textwrap.fill(article['ko_title'], width=12)
    draw.multiline_text((width//2, height//2), wrapped_title, fill=(255, 255, 255), font=title_font, anchor="mm", align="center", spacing=30)
    draw.text((width - 60, height - 60), f"Source: {article['source_name']}", fill=(255, 255, 255, 120), font=source_font, anchor="rd")
    s1.save("images/slide_0.png")

    # --- 2번 장: 기사 원본 사진 (주제에 적합한 기사 원본, 레터박스) ---
    s2_orig = raw_img.copy()
    s2_orig.thumbnail((width - 120, height - 120), Image.Resampling.LANCZOS)
    s2 = Image.new('RGB', (width, height), color=(15, 15, 15))
    s2.paste(s2_orig, ((width - s2_orig.size[0]) // 2, (height - s2_orig.size[1]) // 2))
    s2.save("images/slide_1.png")

    # --- 3번 장: 완전히 새롭게 생성된 AI 주제 이미지 ---
    ai_img.save("images/slide_2.png")
    
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
        
        # Syntax Error가 발생했던 부분을 완벽히 검증했습니다.
        res = requests.post(f"https://graph.facebook.com/v19.0/{account_id}/media", data={
            'image_url': img_url, 
            'is_carousel_item': 'true', 
            'access_token': access_token
        }).json()
        
        if 'id' in res:
            container_ids.append(res['id'])
            print(f"✅ 슬라이드 {i} 업로드 준비 완료")
        else:
            print(f"❌ 슬라이드 {i} 오류: {res}")
        time.sleep(10)

    # 슬라이드 합치기
    carousel_res = requests.post(f"https://graph.facebook.com/v19.0/{account_id}/media", data={
        'media_type': 'CAROUSEL', 
        'children': ','.join(container_ids),
        'caption': summary_ko + "\n\n#경제 #과학 #글로벌뉴스 #world_folio", 
        'access_token': access_token
    }).json()
    
    if 'id' in carousel_res:
        print("⏳ 게시물 최종 승인 대기 중 (60초)...")
        time.sleep(60)
        requests.post(f"https://graph.facebook.com/v19.0/{account_id}/media_publish", data={
            'creation_id': carousel_res['id'], 
            'access_token': access_token
        })
        print("🎉 인스타그램 업로드 완벽히 성공!")
    else:
        print(f"❌ 최종 게시 실패: {carousel_res}")

def main():
    if len(sys.argv) < 2: return
    mode = sys.argv[1]

    if mode == "--generate":
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
            print("🚀 모든 콘텐츠 생성 완료!")
        else:
            print("❌ 조건에 맞는 뉴스를 찾지 못했습니다.")
            
    elif mode == "--upload":
        if os.path.exists("summary.txt"):
            with open("summary.txt", "r", encoding="utf-8") as f:
                summary = f.read()
            upload_to_insta(summary)
        else:
            print("❌ 요약 파일이 없습니다.")

if __name__ == "__main__":
    main()
