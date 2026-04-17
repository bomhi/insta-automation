import os
import requests
import time
import sys
import textwrap
import re
import shutil
import random 
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
from deep_translator import GoogleTranslator
from bs4 import BeautifulSoup

# [설정]
INSTA_ID = "@world_folio"

# [초강력 필터링] 악성/광고성/보안/제휴/금융 면책조항 완벽 차단 리스트
JUNK_PHRASES = [
    # 기존 차단
    'Ben이 스토리를', '받은편지함', '가입', '동의하는', '약관', '개인 정보', 
    'Insider', '뉴스레터', '클릭하면', 'Copyright', 'All rights reserved', '무료 기사',
    '로봇이 아님을', '문의사항', '지원팀에 문의', '구독을 통해', '참조 ID', 'Bloomberg',
    '계속하려면', 'JavaScript', '브라우저', '클릭하여',
    # 제휴 마케팅, 수수료, 광고 안내문 차단
    '이 링크를 통해', '비용을 지불', '특정 활동에 대해', '수수료를 받', '수익을 창출',
    '제휴 링크', '스폰서', '자세히 알아보기', '여기에서 확인', '광고입니다', '당사에',
    'affiliate', 'commission', 'sponsor', 'subscribe', 'sign up', 'click here',
    'read more', 'learn more', 'pays us', 'generated through this link',
    # 금융 매체 법적 면책 조항 및 주의사항 원천 차단
    'Yahoo Finance', '브로커-딜러', '투자 자문', '증권이나 암호화폐', '판매하거나', 
    '거래를 촉진하지', '투자 권유가 아닙니다', '법적 조언', '재무 조언', '투자에 대한 책임',
    '손실에 대해', 'broker-dealer', 'investment advisor', 'financial advice'
]
SKIP_KEYWORDS = ['AP Photo', 'AP 사진', 'Photo/', 'Photograph', 'Caption', '©', '출처:', '연설하고', '손짓을', '재배포 금지']

# [알고리즘 무기 1]: 깨지는 이모지를 제거한 텍스트 후킹 태그
HOOK_TAGS = [
    "GLOBAL ECONOMY HOT ISSUE",
    "비즈니스 필독 지식",
    "전 세계가 주목하는 뉴스",
    "오늘의 마켓 하이라이트",
    "GLOBAL TREND REPORT"
]

# [알고리즘 무기 2]: 댓글 유도형 질문 (캡션용)
ENGAGEMENT_QUESTIONS = [
    "여러분은 이 상황에 대해 어떻게 생각하시나요? 자유롭게 댓글로 의견을 남겨주세요!👇",
    "이 이슈가 우리의 일상에 어떤 영향을 미칠까요? 여러분의 생각을 들려주세요!💬",
    "더 깊이 알고 싶은 점이 있다면 언제든 댓글로 남겨주세요!📝",
    "이 뉴스에 공감하시나요? 주변에 알리고 싶다면 저장과 공유를 잊지 마세요!🔖"
]

# 다이내믹 템플릿
INTROS = [
    "사실이 알려지며 전 세계적인 관심을 모으고 있습니다. 현재 이 사안은 주요 외신들 사이에서도 비중 있게 다뤄지며 다양한 해석을 낳고 있는 상황입니다.",
    "최근 글로벌 시장과 주요 업계의 시선이 이 소식에 집중되고 있습니다. 향후 판도를 바꿀 수 있는 핵심 이슈인 만큼 그 파장에 이목이 쏠립니다.",
    "해당 소식이 전해지면서 전문가들 사이에서 뜨거운 화두로 떠오르고 있습니다. 새로운 트렌드의 변곡점이 될지 시장의 관심이 뜨겁습니다."
]
TRANSITIONS = [
    "특히 이번 과정에서 나타난 특징적인 요소들은 기존의 흐름과는 전혀 다른 양상을 보이고 있어 주목할 만합니다.",
    "무엇보다 이번 사안의 이면에 자리한 전략적 의도와 시장의 즉각적인 반응이 향후 흐름을 가늠할 중요한 잣대가 될 것으로 보입니다.",
    "이러한 움직임은 단순한 해프닝을 넘어, 급변하는 글로벌 정세 속에서 새로운 주도권을 쥐기 위한 발빠른 행보로 풀이됩니다."
]
CONCLUSIONS = [
    "결국 단기적인 성과보다는 고유의 경쟁력과 지속 가능성을 확보하는 것이 향후 가장 중요한 과제가 될 것으로 보입니다.",
    "앞으로의 구체적인 대응 방식과 후속 조치가 어떤 실질적 결과를 낳을지 전 세계가 예의주시해야 할 시점입니다.",
    "기대와 우려가 교차하는 가운데, 향후 뚜렷한 모멘텀을 만들어내며 시장에 안착할 수 있을지가 핵심 관건입니다."
]

def is_valid_paragraph(text):
    text = text.strip()
    if len(text) < 40: return False
    if any(junk in text for junk in JUNK_PHRASES): return False
    if any(kw in text for kw in SKIP_KEYWORDS): return False
    return True

def crawl_full_text(url):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    try:
        res = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        paragraphs = soup.find_all('p')
        valid_paragraphs = [p.get_text().strip() for p in paragraphs if is_valid_paragraph(p.get_text())]
        return " ".join(valid_paragraphs)
    except:
        return None

def get_processed_news():
    print("\n🔍 [1단계: 뉴스 수집 및 초강력 필터링]")
    api_key = os.getenv('NEWS_API_KEY')
    
    urls = [
        f"https://newsapi.org/v2/top-headlines?country=us&category=business&pageSize=15&apiKey={api_key}",
        f"https://newsapi.org/v2/top-headlines?country=us&category=science&pageSize=10&apiKey={api_key}"
    ]
    
    articles = []
    try:
        for url in urls:
            res = requests.get(url)
            res.raise_for_status()
            data = res.json()
            articles.extend([a for a in data.get('articles', []) if a.get('urlToImage') and a.get('url')])
            
        for a in articles:
            full_text = crawl_full_text(a['url'])
            if not full_text or len(full_text) < 300: continue

            translator = GoogleTranslator(source='en', target='ko')
            en_title = a['title'].split(' - ')[0]
            ko_title = translator.translate(en_title)
            
            if len(ko_title) > 32:
                split_title = re.split(r'[,:;]', ko_title)[0].strip()
                if len(split_title) < 15:
                    ko_title = " ".join(ko_title.split(' ')[:6]) # 6어절만 유지
                else:
                    ko_title = split_title
            ko_title = ko_title.replace('...', '').strip()

            ko_full_text = translator.translate(full_text[:2000])
            source_name = a['source']['name'] or "Global News"
            
            # 본문 문장 분리 (유효한 문장만)
            sentences = [s.strip() for s in ko_full_text.split('. ') if len(s) > 30 and not any(j in s for j in JUNK_PHRASES)]
            if len(sentences) < 3: continue

            # 2번 슬라이드에 띄울 '핵심 한 줄 요약' 추출 (보통 첫 문장이 가장 중요)
            core_message = sentences[0]

            intro_text = random.choice(INTROS)
            trans_text = random.choice(TRANSITIONS)
            concl_text = random.choice(CONCLUSIONS)
            hook_text = random.choice(HOOK_TAGS)
            engagement_text = random.choice(ENGAGEMENT_QUESTIONS)

            # 캡션(게시글) 조립
            summary = f"📢 [{ko_title}]\n\n"
            summary += f"{intro_text}\n\n"
            body_text = ". ".join(sentences[0:3])
            summary += f"해당 사안의 구체적인 내용을 살펴보면, {body_text}. {trans_text}\n\n"
            conclusion_text = sentences[3] if len(sentences) > 3 else sentences[-1]
            summary += f"{conclusion_text}. {concl_text}\n\n"
            
            # 캡션 맨 마지막에 댓글 유도 질문 삽입
            summary += f"💡 Q. {engagement_text}"

            return {
                'ko_title': ko_title, 
                'core_message': core_message, 
                'hook_tag': hook_text,        
                'summary_ko': summary, 
                'image_url': a.get('urlToImage'), 
                'source_name': source_name
            }
    except Exception as e:
        print(f"❌ 뉴스 수집 실패: {e}")
    return None

def create_slides(article):
    print("\n🎨 [2단계: 슬라이드 3장 제작 (인스타 피드 크기 최적화 1080x1080)]")
    
    width, height = 1080, 1080
    
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        orig_res = requests.get(article['image_url'], headers=headers, stream=True, timeout=10)
        orig_res.raise_for_status()
        raw_img = Image.open(orig_res.raw).convert('RGB')
    except:
        raw_img = Image.new('RGB', (width, height), color=(35, 40, 45))

    font_path = "NanumSquareR.ttf"
    try:
        title_font = ImageFont.truetype(font_path, 65) 
        hook_font = ImageFont.truetype(font_path, 35)    
        core_font = ImageFont.truetype(font_path, 40)    
        id_font = ImageFont.truetype(font_path, 28)
        source_font = ImageFont.truetype(font_path, 22)
        
        # 3번장 심플 폰트
        cta_main_font = ImageFont.truetype(font_path, 55)
        cta_sub_font = ImageFont.truetype(font_path, 40)
    except:
        title_font = hook_font = core_font = id_font = source_font = cta_main_font = cta_sub_font = ImageFont.load_default()

    # --- 1번 장: 타이틀 (후킹 태그 추가, 어둡게 조정) ---
    s1 = raw_img.copy().resize((width, height), Image.Resampling.LANCZOS).filter(ImageFilter.GaussianBlur(radius=10))
    s1 = ImageEnhance.Brightness(s1).enhance(0.35) 
    draw = ImageDraw.Draw(s1)
    
    draw.text((width - 60, 60), INSTA_ID, fill=(255, 255, 255, 180), font=id_font, anchor="ra")
    
    # 상단 후킹 태그 (노란색으로 시선 강탈, 이모지 없음)
    draw.text((width//2, height//2 - 160), article['hook_tag'], fill=(255, 225, 50), font=hook_font, anchor="mm")
    
    # 메인 타이틀
    wrapped_title = textwrap.fill(article['ko_title'], width=14)
    draw.multiline_text((width//2, height//2 + 20), wrapped_title, fill=(255, 255, 255), font=title_font, anchor="mm", align="center", spacing=25)
    draw.text((width - 60, height - 60), f"Source: {article['source_name']}", fill=(255, 255, 255, 120), font=source_font, anchor="rd")
    s1.save("images/slide_0.png")

    # --- 2번 장: 하단 1/3만 어둡게 하고 뉴스 핵심 텍스트 삽입 ---
    s2_orig = raw_img.copy()
    s2_orig.thumbnail((width - 80, height - 80), Image.Resampling.LANCZOS) 
    s2 = Image.new('RGB', (width, height), color=(20, 20, 20))
    s2.paste(s2_orig, ((width - s2_orig.size[0]) // 2, (height - s2_orig.size[1]) // 2 - 40)) 
    
    overlay = Image.new('RGBA', s2.size, (0, 0, 0, 0))
    draw_overlay = ImageDraw.Draw(overlay)
    
    # 하단 1/3 영역 반투명 블랙 박스 (y: 720 부터 1080 까지)
    box_top = int(height * 0.66)
    draw_overlay.rectangle([0, box_top, width, height], fill=(0, 0, 0, 210))
    
    # 텍스트 이쁘게 줄바꿈 (모바일 가독성)
    wrapped_core = textwrap.fill(article['core_message'], width=24)
    
    # 하단 1/3 영역 중앙에 텍스트 배치
    text_y = box_top + (height - box_top)//2
    draw_overlay.multiline_text((width//2, text_y), wrapped_core, fill=(255, 255, 255, 240), font=core_font, anchor="mm", align="center", spacing=15)
    
    s2 = Image.alpha_composite(s2.convert('RGBA'), overlay).convert('RGB')
    s2.save("images/slide_1.png")

    # --- 3번 장: 심플 화이트 배경 + 파스텔톤 텍스트 CTA ---
    s3 = Image.new('RGB', (width, height), color=(255, 255, 255))
    draw_s3 = ImageDraw.Draw(s3)
    
    pastel_color = (120, 150, 180) 
    draw_s3.text((width//2, 400), "오늘의 브리핑이 유익하셨나요?", fill=pastel_color, font=cta_main_font, anchor="mm")
    
    # [이모지 깨짐 해결] 심플하게 점(·) 기호로 교체
    draw_s3.text((width//2, 530), "좋아요  ·  댓글  ·  저장", fill=(180, 180, 180), font=cta_sub_font, anchor="mm")
    
    draw_s3.text((width//2, 700), f"{INSTA_ID} 팔로우하기", fill=pastel_color, font=cta_sub_font, anchor="mm")

    s3.save("images/slide_2.png")
    
    return ["images/slide_0.png", "images/slide_1.png", "images/slide_2.png"]

def upload_to_insta(summary_ko):
    print("\n📤 [3단계: 인스타그램 최종 게시 (보안 우회 모드)]")
    access_token = os.getenv('INSTA_ACCESS_TOKEN')
    account_id = os.getenv('INSTA_USER_ID')
    user_name = "bomhi" 
    repo_name = "insta-automation" 
    
    container_ids = []
    
    # 1. 개별 슬라이드 컨테이너 업로드 (불규칙한 대기 시간 적용)
    for i in range(3):
        img_url = f"https://raw.githubusercontent.com/{user_name}/{repo_name}/main/images/slide_{i}.png?t={int(time.time())}"
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
            return # 컨테이너 생성 실패 시 멈춤 (비정상 게시 방지)
            
        # [핵심 방어]: 기계처럼 보이지 않도록 15초 ~ 30초 사이 랜덤하게 쉬기
        sleep_time = random.randint(15, 30)
        print(f"   🤖 보안 봇 우회를 위해 {sleep_time}초 대기 중...")
        time.sleep(sleep_time)

    # 2. 캐러셀(슬라이드 묶음) 생성
    carousel_res = requests.post(f"https://graph.facebook.com/v19.0/{account_id}/media", data={
        'media_type': 'CAROUSEL', 
        'children': ','.join(container_ids),
        'caption': summary_ko + "\n\n#경제 #과학 #글로벌뉴스 #world_folio", 
        'access_token': access_token
    }).json()
    
    if 'id' in carousel_res:
        # [핵심 방어]: 캐러셀 생성 후 검수 시간을 충분히 줌 (70~90초 랜덤)
        final_sleep = random.randint(70, 90)
        print(f"⏳ 게시물 최종 승인 대기 중 ({final_sleep}초)...")
        time.sleep(final_sleep)
        
        # 3. 최종 퍼블리시
        publish_res = requests.post(f"https://graph.facebook.com/v19.0/{account_id}/media_publish", data={
            'creation_id': carousel_res['id'], 
            'access_token': access_token
        }).json()
        
        if 'id' in publish_res:
            print("🎉 인스타그램 업로드 완벽히 성공!")
        else:
            print(f"❌ 퍼블리시 실패: {publish_res}")
    else:
        print(f"❌ 캐러셀 생성 실패: {carousel_res}")

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
