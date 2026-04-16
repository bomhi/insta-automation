import os
import requests
import time
import sys
import textwrap
import re
import shutil
import random # [추가됨] 문장 랜덤 조합을 위한 모듈
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
from deep_translator import GoogleTranslator
from bs4 import BeautifulSoup

# [설정]
INSTA_ID = "@world_folio"

# 악성/광고성/보안(캡챠) 문구 완벽 차단 리스트
JUNK_PHRASES = [
    'Ben이 스토리를', '받은편지함', '가입', '동의하는', '약관', '개인 정보', 
    'Insider', '뉴스레터', '클릭하면', 'Copyright', 'All rights reserved', '무료 기사',
    '로봇이 아님을', '문의사항', '지원팀에 문의', '구독을 통해', '참조 ID', 'Bloomberg',
    '계속하려면', 'JavaScript', '브라우저', '클릭하여'
]
SKIP_KEYWORDS = ['AP Photo', 'AP 사진', 'Photo/', 'Photograph', 'Caption', '©', '출처:', '연설하고', '손짓을', '재배포 금지']

# [기능 1]: 경제/IT 뉴스 주요 용어 사전
GLOSSARY_DB = {
    "VC": "벤처 캐피탈 (스타트업 투자사)",
    "IPO": "기업공개 (증시 상장)",
    "Anthropic": "미국의 유력 생성형 AI 개발사",
    "OpenAI": "챗GPT를 개발한 인공지능 기업",
    "M&A": "기업 인수합병",
    "CEO": "최고경영자",
    "Inflation": "물가 상승",
    "Fed": "미국 연방준비제도 (중앙은행)",
    "Startup": "신생 창업기업",
    "Fund": "투자 기금",
    "AI": "인공지능",
    "Tech": "기술 산업"
}

# [기능 2]: 자연스러운 다이내믹 템플릿 (기계적인 반복 방지)
INTROS = [
    "사실이 알려지며 전 세계적인 관심을 모으고 있습니다. 현재 이 사안은 주요 외신들 사이에서도 비중 있게 다뤄지며 다양한 해석을 낳고 있는 상황입니다.",
    "최근 글로벌 시장과 주요 업계의 시선이 이 소식에 집중되고 있습니다. 향후 판도를 바꿀 수 있는 핵심 이슈인 만큼 그 파장에 이목이 쏠립니다.",
    "해당 소식이 전해지면서 전문가들 사이에서 뜨거운 화두로 떠오르고 있습니다. 새로운 트렌드의 변곡점이 될지 시장의 관심이 뜨겁습니다.",
    "국제 사회와 경제 전반에 걸쳐 해당 이슈가 적지 않은 파장을 일으키고 있습니다. 단순한 소식을 넘어 향후 지각 변동을 예고하는 대목입니다."
]

TRANSITIONS = [
    "특히 이번 과정에서 나타난 특징적인 요소들은 기존의 흐름과는 전혀 다른 양상을 보이고 있어 주목할 만합니다.",
    "무엇보다 이번 사안의 이면에 자리한 전략적 의도와 시장의 즉각적인 반응이 향후 흐름을 가늠할 중요한 잣대가 될 것으로 보입니다.",
    "이러한 움직임은 단순한 해프닝을 넘어, 급변하는 글로벌 정세 속에서 새로운 주도권을 쥐기 위한 발빠른 행보로 풀이됩니다.",
    "전문가들은 이 같은 변화가 관련 산업 및 경제 전반에 걸쳐 새로운 연쇄 작용을 촉발할 가능성이 높다고 분석하고 있습니다."
]

CONCLUSIONS = [
    "결국 단기적인 성과보다는 고유의 경쟁력과 지속 가능성을 확보하는 것이 향후 가장 중요한 과제가 될 것으로 보입니다.",
    "앞으로의 구체적인 대응 방식과 후속 조치가 어떤 실질적 결과를 낳을지 전 세계가 예의주시해야 할 시점입니다.",
    "기대와 우려가 교차하는 가운데, 향후 뚜렷한 모멘텀을 만들어내며 시장에 안착할 수 있을지가 핵심 관건입니다.",
    "결과적으로 이번 이슈는 앞으로 다가올 거대한 변화의 신호탄일 수 있으며, 이에 대한 철저한 대비와 전략적 접근이 필요해 보입니다."
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
    print("\n🔍 [1단계: 뉴스 수집 및 다이내믹 문맥 조합]")
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
                    ko_title = " ".join(ko_title.split(' ')[:6])
                else:
                    ko_title = split_title
            ko_title = ko_title.replace('...', '').strip()

            ko_full_text = translator.translate(full_text[:2000])
            source_name = a['source']['name'] or "Global News"
            
            sentences = [s.strip() for s in ko_full_text.split('. ') if len(s) > 30 and not any(j in s for j in JUNK_PHRASES)]
            if len(sentences) < 3: continue

            # --- [수정됨]: 문맥 랜덤 조합으로 매번 다른 스타일 연출 ---
            intro_text = random.choice(INTROS)
            trans_text = random.choice(TRANSITIONS)
            concl_text = random.choice(CONCLUSIONS)

            summary = f"📢 [{ko_title}]\n\n"
            summary += f"{intro_text}\n\n"
            
            body_text = ". ".join(sentences[0:3])
            summary += f"해당 사안의 구체적인 내용을 살펴보면, {body_text}. {trans_text}\n\n"
            
            conclusion_text = sentences[3] if len(sentences) > 3 else sentences[-1]
            summary += f"{conclusion_text}. {concl_text}\n\n"
            summary += "간단히 보기"

            glossary_list = []
            for key, value in GLOSSARY_DB.items():
                if re.search(r'\b' + re.escape(key) + r'\b', en_title, re.IGNORECASE):
                    glossary_list.append(f"{key} : {value}")
            glossary_text = " / ".join(glossary_list)

            return {
                'ko_title': ko_title, 
                'glossary_text': glossary_text,
                'summary_ko': summary, 
                'image_url': a.get('urlToImage'), 
                'source_name': source_name
            }
    except Exception as e:
        print(f"❌ 뉴스 수집 실패: {e}")
    return None

def create_slides(article):
    print("\n🎨 [2단계: 슬라이드 3장 제작 (심플 화이트 CTA 포함)]")
    width, height = 1080, 1080
    
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        orig_res = requests.get(article['image_url'], headers=headers, stream=True, timeout=10)
        orig_res.raise_for_status()
        raw_img = Image.open(orig_res.raw).convert('RGB')
    except:
        raw_img = Image.new('RGB', (width, height), color=(245, 245, 245))

    font_path = "NanumSquareR.ttf"
    try:
        title_font = ImageFont.truetype(font_path, 65) 
        id_font = ImageFont.truetype(font_path, 28)
        source_font = ImageFont.truetype(font_path, 22)
        glossary_font = ImageFont.truetype(font_path, 20)
        
        # 3번장 심플 폰트
        cta_main_font = ImageFont.truetype(font_path, 55)
        cta_sub_font = ImageFont.truetype(font_path, 40)
    except:
        title_font = id_font = source_font = glossary_font = cta_main_font = cta_sub_font = ImageFont.load_default()

    # --- 1번 장: 타이틀 ---
    s1 = raw_img.copy().resize((width, height), Image.Resampling.LANCZOS).filter(ImageFilter.GaussianBlur(radius=10))
    s1 = ImageEnhance.Brightness(s1).enhance(0.4)
    draw = ImageDraw.Draw(s1)
    draw.text((width - 60, 60), INSTA_ID, fill=(255, 255, 255, 180), font=id_font, anchor="ra")
    wrapped_title = textwrap.fill(article['ko_title'], width=14)
    draw.multiline_text((width//2, height//2), wrapped_title, fill=(255, 255, 255), font=title_font, anchor="mm", align="center", spacing=30)
    draw.text((width - 60, height - 60), f"Source: {article['source_name']}", fill=(255, 255, 255, 120), font=source_font, anchor="rd")
    s1.save("images/slide_0.png")

    # --- 2번 장: 기사 사진 + 용어 사전 ---
    s2_orig = raw_img.copy()
    s2_orig.thumbnail((width - 120, height - 120), Image.Resampling.LANCZOS)
    s2 = Image.new('RGB', (width, height), color=(15, 15, 15))
    s2.paste(s2_orig, ((width - s2_orig.size[0]) // 2, (height - s2_orig.size[1]) // 2))
    
    if article['glossary_text']:
        overlay = Image.new('RGBA', s2.size, (0, 0, 0, 0))
        draw_overlay = ImageDraw.Draw(overlay)
        g_text = f"💡 용어 사전 | {article['glossary_text']}"
        bbox = draw_overlay.multiline_textbbox((width//2, height - 90), g_text, font=glossary_font, anchor="ms", align="center")
        draw_overlay.rounded_rectangle([bbox[0]-25, bbox[1]-15, bbox[2]+25, bbox[3]+15], fill=(0, 0, 0, 200), radius=12)
        draw_overlay.multiline_text((width//2, height - 90), g_text, fill=(255, 255, 255, 240), font=glossary_font, anchor="ms", align="center")
        s2 = Image.alpha_composite(s2.convert('RGBA'), overlay).convert('RGB')
    s2.save("images/slide_1.png")

    # --- 3번 장: 심플 화이트 배경 + 파스텔톤 텍스트 CTA ---
    s3 = Image.new('RGB', (width, height), color=(255, 255, 255))
    draw_s3 = ImageDraw.Draw(s3)
    
    pastel_color = (120, 150, 180) 
    
    draw_s3.text((width//2, 400), "오늘의 브리핑이 유익하셨나요?", fill=pastel_color, font=cta_main_font, anchor="mm")
    draw_s3.text((width//2, 530), "❤️ 좋아요   💬 댓글   🔖 저장", fill=(180, 180, 180), font=cta_sub_font, anchor="mm")
    draw_s3.text((width//2, 700), f"{INSTA_ID} 팔로우하기", fill=pastel_color, font=cta_sub_font, anchor="mm")

    s3.save("images/slide_2.png")
    
    return ["images/slide_0.png", "images/slide_1.png", "images/slide_2.png"]

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

    carousel_res = requests.post(f"https://graph.facebook.com/v19.0/{account_id}/media", data={
        'media_type': 'CAROUSEL', 'children': ','.join(container_ids),
        'caption': summary_ko + "\n\n#경제 #과학 #글로벌뉴스 #world_folio", 'access_token': access_token
    }).json()
    
    if 'id' in carousel_res:
        time.sleep(60)
        requests.post(f"https://graph.facebook.com/v19.0/{account_id}/media_publish", data={'creation_id': carousel_res['id'], 'access_token': access_token})
        print("🎉 인스타그램 업로드 성공!")

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
            print("🚀 콘텐츠 생성 완료!")
    elif mode == "--upload":
        if os.path.exists("summary.txt"):
            with open("summary.txt", "r", encoding="utf-8") as f:
                summary = f.read()
            upload_to_insta(summary)

if __name__ == "__main__":
    main()
