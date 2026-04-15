import os
import requests
import time
import sys
import textwrap
import random
import shutil
from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
from deep_translator import GoogleTranslator

# [설정 및 검증 리스트]
INSTA_ID = "@world_folio"
SOFT_BLACKLIST = ['brutal', 'mutilated', 'disturbing', 'graphic', 'gore', 'suicide']

def get_processed_news():
    print("\n🔍 [1단계: 뉴스 수집 및 가독성 기반 검증]")
    api_key = os.getenv('NEWS_API_KEY')
    # 다양성 확보를 위해 20개를 가져와 검증합니다.
    url = f"https://newsapi.org/v2/top-headlines?country=us&pageSize=20&apiKey={api_key}"
    
    try:
        data = requests.get(url).json()
        articles = [a for a in data.get('articles', []) if a.get('urlToImage') and a.get('description')]
        
        for a in articles:
            check_text = (a['title'] + a['description']).lower()
            if any(word in check_text for word in SOFT_BLACKLIST):
                continue
            
            translator = GoogleTranslator(source='en', target='ko')
            ko_title = translator.translate(a['title'])
            ko_desc = translator.translate(a['description'])
            # 출처 정보 추출 (예: BBC News, Reuters)
            source_name = a['source']['name'] or "알 수 없는 출처"
            
            # 본문 가독성 요약 (분량 확보: 최대 10줄 내외)
            summary = f"📍 {ko_title}\n\n"
            sentences = [s.strip() for s in ko_desc.split('. ') if len(s) > 10]
            for s in sentences[:8]: 
                summary += f"• {s}.\n"
            
            print(f"✅ 기사 선정: {ko_title[:30]}... (출처: {source_name})")
            
            return {
                'ko_title': ko_title, 
                'summary_ko': summary, 
                'image_url': a.get('urlToImage'),
                'source_name': source_name # 출처 정보 추가
            }
    except Exception as e:
        print(f"❌ 뉴스 수집 오류: {e}")
    return None

def create_slides(article):
    print("\n🎨 [2단계: 2장 슬라이드 생성 및 시각화]")
    width, height = 1080, 1080
    image_paths = []
    
    try:
        res = requests.get(article['image_url'], stream=True, timeout=10)
        raw_img = Image.open(res.raw).convert('RGB')
    except:
        raw_img = Image.new('RGB', (width, height), color=(35, 35, 35))

    font_path = "NanumSquareR.ttf"
    try:
        title_font = ImageFont.truetype(font_path, 72)
        id_font = ImageFont.truetype(font_path, 26) # 작게
        # 출처 폰트 크기 (아이디보다 더 작게: 26 -> 20)
        source_font = ImageFont.truetype(font_path, 20) 
    except:
        title_font = id_font = source_font = ImageFont.load_default()

    # --- 슬라이드 1: 타이틀 카드 (시각화 + 정보 배치) ---
    print("📸 슬라이드 1(타이틀 카드) 생성 중...")
    
    # 1. 뉴스 사진을 생성된 이미지처럼 변형 (Deep Blur + Color Overlay)
    # 꽉 차게 리사이즈
    s1 = raw_img.copy().resize((width, height), Image.Resampling.LANCZOS)
    # 아주 강한 블러 (마치 추상화처럼)
    s1 = s1.filter(ImageFilter.GaussianBlur(radius=35))
    # 어둡게
    s1 = ImageEnhance.Brightness(s1).enhance(0.25)
    
    # 랜덤 색상 오버레이를 추가하여 더욱 '생성된 이미지' 느낌 부여 (선택 사항)
    overlay = Image.new('RGB', (width, height), color=(random.randint(0,50), random.randint(0,50), random.randint(30,80))) # 랜덤한 어두운 톤
    s1 = Image.blend(s1, overlay, alpha=0.3)
    
    draw = ImageDraw.Draw(s1)
    
    # [텍스트 배치 1] 우측 상단 아이디 (작고 은은하게)
    draw.text((width - 60, 60), INSTA_ID, fill=(255, 255, 255, 120), font=id_font, anchor="ra")
    
    # [텍스트 배치 2] 제목 (중앙 배치)
    wrapped_title = textwrap.fill(article['ko_title'], width=14)
    draw.multiline_text((width//2, height//2), wrapped_title, fill=(255, 255, 255), 
                        font=title_font, anchor="mm", align="center", spacing=25)
    
    # [텍스트 배치 3] 우측 하단 출처 (아이디보다 작고 투명하게)
    source_text = f"출처: {article['source_name']}"
    draw.text((width - 50, height - 50), source_text, fill=(255, 255, 255, 90), font=source_font, anchor="rd")
    
    path1 = "images/slide_0.png"
    s1.save(path1, quality=95)
    image_paths.append(path1)
    
    # --- 슬라이드 2: 메인 기사 사진 (원본) ---
    print("📸 슬라이드 2(메인 사진) 생성 중...")
    
    # 원본 사진을 비율 손상 없이 Letterbox 스타일로 배치 (꽉 차게 크롭하지 않음)
    s2_orig = raw_img.copy()
    s2_orig.thumbnail((width - 100, height - 100), Image.Resampling.LANCZOS) # 여백 확보
    
    # 어두운 배경 생성
    bg = Image.new('RGB', (width, height), color=(15, 15, 15))
    # 중앙에 사진 paste
    bg.paste(s2_orig, ((width - s2_orig.size[0]) // 2, (height - s2_orig.size[1]) // 2))
    s2 = bg
    
    path2 = "images/slide_1.png"
    s2.save(path2, quality=95)
    image_paths.append(path2)
    
    print(f"✅ 총 2장의 슬라이드가 생성 및 저장되었습니다.")
    return image_paths

def main():
    if len(sys.argv) < 2: return
    mode = sys.argv[1]

    if mode == "--generate":
        # [이미지 폴더 자동 청소 로직 추가]
        if os.path.exists("images"):
            print("🧹 기존 이미지 폴더를 비웁니다...")
            shutil.rmtree("images") # 폴더 통째로 삭제
        os.makedirs("images") # 다시 깨끗한 폴더 생성
        
        data = get_processed_news()
        if data:
            create_slides(data)
            with open("summary.txt", "w", encoding="utf-8") as f:
                f.write(data['summary_ko'])
            print("\n✅ 기존 사진 삭제 후 새 콘텐츠 준비 완료!")

    elif mode == "--upload":
        if os.path.exists("summary.txt"):
            with open("summary.txt", "r", encoding="utf-8") as f:
                summary = f.read()
            upload_to_insta(summary)

def upload_to_insta(summary_ko):
    print("\n📤 [3단계: 인스타그램 최종 게시]")
    access_token = os.getenv('INSTA_ACCESS_TOKEN')
    account_id = os.getenv('INSTA_USER_ID')
    user_name = "bomhi"
    repo_name = "insta-automation"
    
    container_ids = []
    # 3장 -> 2장으로 루프 횟수 변경
    for i in range(2):
        img_url = f"https://raw.githubusercontent.com/{user_name}/{repo_name}/main/images/slide_{i}.png?t={int(time.time())}"
        print(f"이미지 컨테이너 {i+1}/2 생성 중...")
        res = requests.post(f"https://graph.facebook.com/v19.0/{account_id}/media", data={
            'image_url': img_url, 'is_carousel_item': 'true', 'access_token': access_token
        }).json()
        if 'id' in res: container_ids.append(res['id'])
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
        requests.post(f"https://graph.facebook.com/v19.0/{account_id}/media_publish", data={
            'creation_id': carousel_res['id'], 'access_token': access_token
        })
        print("🎉 인스타그램 게시가 완료되었습니다!")

if __name__ == "__main__":
    main()
