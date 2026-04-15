import os
import requests
import time
import sys
import textwrap
from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
from deep_translator import GoogleTranslator

# [설정]
INSTA_ID = "@world_folio"
SOFT_BLACKLIST = ['brutal', 'mutilated', 'disturbing', 'graphic', 'gore', 'suicide']

def get_processed_news():
    print("\n🔍 [1단계: 뉴스 수집 및 내용 검증]")
    api_key = os.getenv('NEWS_API_KEY')
    # 더 다양한 기사를 위해 20개를 가져와 검증합니다.
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
            
            # 본문 분량 대폭 증가 (최대 10줄 이내 가독성 확보)
            summary = f"📍 {ko_title}\n\n"
            sentences = [s.strip() for s in ko_desc.split('. ') if len(s) > 10]
            for s in sentences[:7]: 
                summary += f"• {s}.\n"
            
            print(f"✅ 검증 완료: {ko_title[:30]}...")
            return {'ko_title': ko_title, 'summary_ko': summary, 'image_url': a.get('urlToImage')}
    except Exception as e:
        print(f"❌ 뉴스 수집 실패: {e}")
    return None

def create_slides(article):
    print("\n🎨 [2단계: 이미지 생성 및 디자인 검증]")
    width, height = 1080, 1080
    image_paths = []
    
    try:
        res = requests.get(article['image_url'], stream=True, timeout=10)
        raw_img = Image.open(res.raw).convert('RGB')
    except:
        raw_img = Image.new('RGB', (width, height), color=(40, 40, 40))

    font_path = "NanumSquareR.ttf"
    try:
        title_font = ImageFont.truetype(font_path, 70)
        # 아이디 폰트 크기 축소 (40 -> 25) 및 투명도 조절
        id_font = ImageFont.truetype(font_path, 25)
    except:
        title_font = id_font = ImageFont.load_default()

    for i in range(3):
        slide = raw_img.copy()
        
        if i == 0: # 1번 슬라이드: 메인 디자인
            slide = slide.resize((width, height), Image.Resampling.LANCZOS)
            slide = slide.filter(ImageFilter.GaussianBlur(radius=20))
            slide = ImageEnhance.Brightness(slide).enhance(0.4)
            draw = ImageDraw.Draw(slide)
            
            # [아이디 추가] 더 작고 은은하게 우측 상단 배치
            draw.text((width - 60, 60), INSTA_ID, fill=(255, 255, 255, 120), font=id_font, anchor="ra")
            
            # [제목 추가]
            wrapped_title = textwrap.fill(article['ko_title'], width=14)
            draw.multiline_text((width//2, height//2), wrapped_title, fill=(255, 255, 255), 
                                font=title_font, anchor="mm", align="center", spacing=25)
            
        elif i == 1: # 2번 슬라이드: 줌 인(Zoom) 효과
            w, h = slide.size
            min_dim = min(w, h)
            slide = slide.crop(((w-min_dim)//2, (h-min_dim)//2, (w+min_dim)//2, (h+min_dim)//2))
            slide = slide.resize((width, height), Image.Resampling.LANCZOS)
            
        else: # 3번 슬라이드: 여백 디자인
            slide.thumbnail((width - 120, height - 120), Image.Resampling.LANCZOS)
            bg = Image.new('RGB', (width, height), color=(15, 15, 15))
            bg.paste(slide, ((width - slide.size[0]) // 2, (height - slide.size[1]) // 2))
            slide = bg

        path = f"images/slide_{i}.png"
        slide.save(path, quality=95)
        image_paths.append(path)
        print(f"📸 슬라이드 {i+1} 생성 및 저장 완료")
        
    return image_paths

def main():
    if len(sys.argv) < 2: return
    mode = sys.argv[1]

    if mode == "--generate":
        if not os.path.exists("images"): os.makedirs("images")
        data = get_processed_news()
        if data:
            create_slides(data)
            with open("summary.txt", "w", encoding="utf-8") as f:
                f.write(data['summary_ko'])
            print("\n✅ 이미지와 요약문이 GitHub에 준비되었습니다. 저장소에서 확인해 주세요!")

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
    for i in range(3):
        img_url = f"https://raw.githubusercontent.com/{user_name}/{repo_name}/main/images/slide_{i}.png?t={int(time.time())}"
        res = requests.post(f"https://graph.facebook.com/v19.0/{account_id}/media", data={
            'image_url': img_url, 'is_carousel_item': 'true', 'access_token': access_token
        }).json()
        if 'id' in res: container_ids.append(res['id'])
        time.sleep(10)

    caption = f"🌍 오늘의 글로벌 핵심 브리핑\n\n{summary_ko}\n\n#뉴스 #세계뉴스 #해외뉴스 #world_folio"
    
    carousel_res = requests.post(f"https://graph.facebook.com/v19.0/{account_id}/media", data={
        'media_type': 'CAROUSEL', 'children': ','.join(container_ids),
        'caption': caption, 'access_token': access_token
    }).json()
    
    if 'id' in carousel_res:
        time.sleep(60)
        requests.post(f"https://graph.facebook.com/v19.0/{account_id}/media_publish", data={
            'creation_id': carousel_res['id'], 'access_token': access_token
        })
        print("🎉 인스타그램 게시 완료!")

if __name__ == "__main__":
    main()
