import os
import requests
import time
import sys
import textwrap
import re
import shutil
import random 
import urllib.parse
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
from deep_translator import GoogleTranslator
from bs4 import BeautifulSoup

# [설정]
INSTA_ID = "@world_folio"

JUNK_PHRASES = [
    'Ben이 스토리를', '받은편지함', '가입', '동의하는', '약관', '개인 정보', 
    'Insider', '뉴스레터', '클릭하면', 'Copyright', 'All rights reserved', '무료 기사',
    '로봇이 아님을', '문의사항', '지원팀에 문의', '구독을 통해', '참조 ID', 'Bloomberg',
    '계속하려면', 'JavaScript', '브라우저', '클릭하여',
    '이 링크를 통해', '비용을 지불', '특정 활동에 대해', '수수료를 받', '수익을 창출',
    '제휴 링크', '스폰서', '자세히 알아보기', '여기에서 확인', '광고입니다', '당사에',
    'affiliate', 'commission', 'sponsor', 'subscribe', 'sign up', 'click here',
    'read more', 'learn more', 'pays us', 'generated through this link',
    'Yahoo Finance', '브로커-딜러', '투자 자문', '증권이나 암호화폐', '판매하거나', 
    '거래를 촉진하지', '투자 권유가 아닙니다', '법적 조언', '재무 조언', '투자에 대한 책임',
    '손실에 대해', 'broker-dealer', 'investment advisor', 'financial advice',
    '작성자', '특파원', '기자='
]
SKIP_KEYWORDS = ['AP Photo', 'AP 사진', 'Photo/', 'Photograph', 'Caption', '©', '출처:', '연설하고', '손짓을', '재배포 금지']

HOOK_TAGS = [
    "GLOBAL ECONOMY HOT ISSUE",
    "비즈니스 필독 지식",
    "전 세계가 주목하는 뉴스",
    "오늘의 마켓 하이라이트",
    "GLOBAL TREND REPORT"
]

ENGAGEMENT_QUESTIONS = [
    "여러분은 이 상황에 대해 어떻게 생각하시나요? 자유롭게 댓글로 의견을 남겨주세요!👇",
    "이 이슈가 우리의 일상에 어떤 영향을 미칠까요? 여러분의 생각을 들려주세요!💬",
    "더 깊이 알고 싶은 점이 있다면 언제든 댓글로 남겨주세요!📝",
    "이 뉴스에 공감하시나요? 주변에 알리고 싶다면 저장과 공유를 잊지 마세요!🔖"
]

INTROS = [
    "최근 글로벌 시장을 뒤흔들며 전 세계의 이목이 집중되고 있는 핵심 이슈입니다.",
    "해당 소식이 전해지면서 관련 업계와 글로벌 투자자들 사이에서 뜨거운 화두로 떠올랐습니다.",
    "현재 주요 외신들 사이에서도 앞다투어 비중 있게 다뤄지며 향후 파장에 대한 다양한 해석이 나오고 있습니다.",
    "단순한 해프닝을 넘어 글로벌 트렌드의 새로운 변곡점이 될 수 있다는 분석이 제기되고 있습니다.",
    "시장의 예상을 뛰어넘는 전개로 인해 전 세계적인 관심이 쏠리고 있는 상황입니다."
]

BODY_PREFIXES = [
    "구체적인 내용을 살펴보면,",
    "이번 사안의 핵심을 요약하자면,",
    "현지 주요 보도와 전문가들의 분석에 따르면,",
    "자세한 내막을 들여다보면,",
    "시장이 가장 크게 주목하는 부분을 짚어보면,"
]

TRANSITIONS = [
    "특히 이번 과정에서 나타난 특징적인 요소들은 기존의 흐름과는 완전히 다른 양상을 보이고 있어 주목할 만합니다.",
    "무엇보다 이면에 자리한 전략적 의도와 시장의 즉각적인 반응이 향후 흐름을 가늠할 중요한 잣대가 될 것으로 보입니다.",
    "이러한 움직임은 단순한 소식을 넘어, 새로운 주도권을 쥐기 위한 글로벌 기업들의 발빠른 행보로 풀이됩니다.",
    "전문가들은 이 같은 변화가 관련 산업 및 경제 전반에 새로운 연쇄 작용을 촉발할 가능성이 높다고 분석합니다."
]

CONCLUSIONS = [
    "결국 단기적인 성과보다는 고유의 경쟁력과 지속 가능성을 확보하는 것이 향후 가장 중요한 과제가 될 전망입니다.",
    "앞으로의 구체적인 대응 방식과 후속 조치가 어떤 실질적 결과를 낳을지 전 세계가 예의주시해야 할 시점입니다.",
    "기대와 우려가 교차하는 가운데, 시장에 어떻게 안착할 수 있을지가 앞으로의 핵심 관건입니다.",
    "결과적으로 이번 이슈는 다가올 거대한 변화의 신호탄일 수 있으며, 철저한 대비와 전략적 접근이 필요해 보입니다."
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

# [수정: 제목 자연스러움 강화]
def smart_translate_title(text):
    prompt = f"As an expert Instagram news editor, summarize this English headline into a highly clickable, natural Korean magazine headline. Rule 1: Length must be 15 to 30 characters. Rule 2: Form a natural phrase, NOT just disconnected keywords. Rule 3: Must end with a noun (e.g., '급락', '경고', '발표', '혁신', '성공'). Output ONLY the Korean text. Text: {text}"
    
    ko_title = ""
    for _ in range(3):
        try:
            res = requests.get(f"https://text.pollinations.ai/prompt/{urllib.parse.quote(prompt)}", timeout=12)
            res.raise_for_status()
            ko_text = re.sub(r'[*"\'\[\]]', '', res.text.strip())
            if ko_text and len(ko_text) >= 5 and "Translate" not in ko_text and "Rule" not in ko_text:
                ko_title = ko_text
                break
        except Exception:
            time.sleep(1)
            pass
    
    if not ko_title:
        ko_title = GoogleTranslator(source='en', target='ko').translate(text)
        ko_title = ko_title.replace("다이빙을 공유", "주가 급락").replace("공유가 다이빙", "주가 급락").replace("물러나면서", "사임")
        
        ko_title = re.sub(r'(\S+면서|\S+따르면|\S+밝힌 가운데)\s', '', ko_title)
        ko_title = re.sub(r'(했다|합니다|하다|했습니다|할 것|예정이다|된다|된다고|밝혔다|보인다|경고했다|주장했다|말했다|동결됐다|나타났다|전망이다)$', '', ko_title).strip()
        ko_title = re.sub(r'[은는이가를을에의]$', '', ko_title).strip()
        
        if len(ko_title) > 25:
            words = ko_title.split()
            safe_title = ""
            for word in words:
                if len(safe_title) + len(word) > 22:
                    break
                safe_title += word + " "
            ko_title = safe_title.strip() + "..."
            
    return ko_title

# [수정: 과학 번역 추가 & 존댓말 강제]
def smart_translate_body(text):
    prompt = f"Translate this financial/tech/science news into a highly professional Korean journalistic style. Accurately translate idioms (e.g., 'shares dive' -> '주가 급락', 'breakthrough' -> '획기적 발견'). MUST use polite and formal Korean endings ('~습니다', '~합니다') exclusively. Do not mix informal endings like '~했다'. Output ONLY the Korean text. Text: {text}"
    for _ in range(2):
        try:
            res = requests.get(f"https://text.pollinations.ai/prompt/{urllib.parse.quote(prompt)}", timeout=15)
            res.raise_for_status()
            ko_text = res.text.strip()
            if ko_text and len(ko_text) > 10 and "Translate" not in ko_text:
                return ko_text
        except Exception:
            time.sleep(1)
            pass
    return GoogleTranslator(source='en', target='ko').translate(text)

def process_single_article(article_data):
    full_text = crawl_full_text(article_data['url'])
    if not full_text or len(full_text) < 300: return None

    # [수정: 기자명, 통신사명 사전 살균 (By John Doe, Reuters 등 제거)]
    full_text = re.sub(r'^(By\s[A-Za-z\s]+|Reuters|Bloomberg|AP)\s*[-:]\s*', '', full_text, flags=re.IGNORECASE)

    en_title = article_data['title'].split(' - ')[0]
    ko_title = smart_translate_title(en_title)
    ko_full_text = smart_translate_body(full_text[:1500])
    
    # [수정: 20여 가지 반말(신문체) -> 존댓말 강제 변환 패치]
    ko_full_text = ko_full_text.replace("수익 편지", "실적 발표 서한")\
                               .replace("수익 보고서", "실적 보고서")\
                               .replace("다이빙을 공유", "주가 급락")\
                               .replace("했다.", "했습니다.").replace("한다.", "합니다.")\
                               .replace("된다.", "됩니다.").replace("이다.", "입니다.")\
                               .replace("밝혔다.", "밝혔습니다.").replace("말했다.", "말했습니다.")\
                               .replace("나타났다.", "나타났습니다.").replace("예정이다.", "예정입니다.")\
                               .replace("전망이다.", "전망입니다.").replace("보인다.", "보입니다.")\
                               .replace("않았다.", "않았습니다.").replace("없다.", "없습니다.")\
                               .replace("있다.", "있습니다.").replace("기록했다.", "기록했습니다.")\
                               .replace("발표했다.", "발표했습니다.").replace("전망했다.", "전망했습니다.")\
                               .replace("분석했다.", "분석했습니다.").replace("성공했다.", "성공했습니다.")\
                               .replace("급락했다.", "급락했습니다.").replace("상승했다.", "상승했습니다.")\
                               .replace("하락했다.", "하락했습니다.").replace("증가했다.", "증가했습니다.")\
                               .replace("감소했다.", "감소했습니다.")

    source_name = article_data['source']['name'] or "Global News"
    
    sentences = [s.strip() for s in ko_full_text.split('. ') if len(s) > 30 and not any(j in s for j in JUNK_PHRASES)]
    if len(sentences) < 3: return None

    core_message = sentences[0]

    intro_text = random.choice(INTROS)
    body_prefix = random.choice(BODY_PREFIXES)
    trans_text = random.choice(TRANSITIONS)
    concl_text = random.choice(CONCLUSIONS)
    hook_text = random.choice(HOOK_TAGS)
    engagement_text = random.choice(ENGAGEMENT_QUESTIONS)

    summary = f"📢 [{ko_title}]\n\n"
    summary += f"{intro_text}\n\n"
    body_text = ". ".join(sentences[0:3])
    summary += f"{body_prefix} {body_text}. {trans_text}\n\n"
    conclusion_text = sentences[3] if len(sentences) > 3 else sentences[-1]
    summary += f"{conclusion_text}. {concl_text}\n\n"
    summary += f"💡 Q. {engagement_text}"

    return {
        'ko_title': ko_title, 
        'core_message': core_message, 
        'hook_tag': hook_text,        
        'summary_ko': summary, 
        'image_url': article_data.get('urlToImage'), 
        'source_name': source_name
    }

def get_processed_news():
    print("\n🔍 [1단계: 투트랙(경제/과학) 뉴스 동시 수집 중...]")
    api_key = os.getenv('NEWS_API_KEY')
    
    b_url = f"https://newsapi.org/v2/top-headlines?country=us&category=business&pageSize=10&apiKey={api_key}"
    s_url = f"https://newsapi.org/v2/top-headlines?country=us&category=science&pageSize=10&apiKey={api_key}"
    
    biz_result = None
    sci_result = None
    
    try:
        b_res = requests.get(b_url).json()
        for a in b_res.get('articles', []):
            if a.get('urlToImage') and a.get('url'):
                biz_result = process_single_article(a)
                if biz_result: break
                
        s_res = requests.get(s_url).json()
        for a in s_res.get('articles', []):
            if a.get('urlToImage') and a.get('url'):
                sci_result = process_single_article(a)
                if sci_result: break
    except Exception as e:
        print(f"❌ 뉴스 리스트 가져오기 실패: {e}")

    return biz_result, sci_result

def create_slides(article, prefix):
    print(f"\n🎨 [2단계: {prefix.upper()} 슬라이드 3장 제작 중...]")
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
        title_font = ImageFont.truetype(font_path, 80) 
        hook_font = ImageFont.truetype(font_path, 35)   
        core_font = ImageFont.truetype(font_path, 40)   
        id_font = ImageFont.truetype(font_path, 28)
        source_font = ImageFont.truetype(font_path, 22)
        cta_main_font = ImageFont.truetype(font_path, 55)
        cta_sub_font = ImageFont.truetype(font_path, 40)
    except:
        title_font = hook_font = core_font = id_font = source_font = cta_main_font = cta_sub_font = ImageFont.load_default()

    s1 = raw_img.copy().resize((width, height), Image.Resampling.LANCZOS).filter(ImageFilter.GaussianBlur(radius=10))
    s1 = ImageEnhance.Brightness(s1).enhance(0.35) 
    draw = ImageDraw.Draw(s1)
    
    draw.text((width - 60, 60), INSTA_ID, fill=(255, 255, 255, 180), font=id_font, anchor="ra")
    draw.text((width//2, 180), article['hook_tag'], fill=(255, 225, 50), font=hook_font, anchor="mm")
    
    wrapped_title = textwrap.fill(article['ko_title'], width=12)
    draw.multiline_text((width//2, height//2 + 20), wrapped_title, fill=(255, 255, 255), font=title_font, anchor="mm", align="center", spacing=25)
    
    draw.text((width - 60, height - 60), f"Source: {article['source_name']}", fill=(255, 255, 255, 120), font=source_font, anchor="rd")
    s1.save(f"images/{prefix}_slide_0.png")

    s2 = raw_img.copy().resize((width, height), Image.Resampling.LANCZOS) 
    overlay = Image.new('RGBA', s2.size, (0, 0, 0, 0))
    draw_overlay = ImageDraw.Draw(overlay)
    
    start_y = int(height * 0.40)
    for y in range(start_y, height):
        alpha = int(240 * ((y - start_y) / (height - start_y)))
        draw_overlay.line([(0, y), (width, y)], fill=(0, 0, 0, alpha))
    
    wrapped_core = textwrap.fill(article['core_message'], width=24)
    text_y = int(height * 0.75)
    draw_overlay.multiline_text((width//2, text_y), wrapped_core, fill=(255, 255, 255, 250), font=core_font, anchor="mm", align="center", spacing=15)
    
    s2 = Image.alpha_composite(s2.convert('RGBA'), overlay).convert('RGB')
    s2.save(f"images/{prefix}_slide_1.png")

    s3 = Image.new('RGB', (width, height), color=(255, 255, 255))
    draw_s3 = ImageDraw.Draw(s3)
    
    pastel_color = (120, 150, 180) 
    draw_s3.text((width//2, 400), "오늘의 브리핑이 유익하셨나요?", fill=pastel_color, font=cta_main_font, anchor="mm")
    draw_s3.text((width//2, 530), "좋아요  ·  댓글  ·  저장", fill=(180, 180, 180), font=cta_sub_font, anchor="mm")
    draw_s3.text((width//2, 700), f"{INSTA_ID} 팔로우하기", fill=pastel_color, font=cta_sub_font, anchor="mm")

    s3.save(f"images/{prefix}_slide_2.png")

def upload_to_insta():
    print("\n📤 [3단계: 인스타그램 최종 게시 (선택적 업로드)]")
    
    biz_exists = os.path.exists("biz_summary.txt")
    sci_exists = os.path.exists("sci_summary.txt")
    
    if biz_exists and sci_exists:
        print("❌ [경고] 경제(biz)와 과학(sci) 파일이 둘 다 존재합니다!")
        print("💡 깃허브에서 오늘 업로드하지 않을 카테고리의 '_summary.txt' 파일을 삭제한 뒤 다시 Upload를 돌려주세요.")
        sys.exit(1)
    elif biz_exists:
        prefix = "biz"
        with open("biz_summary.txt", "r", encoding="utf-8") as f: summary_ko = f.read()
    elif sci_exists:
        prefix = "sci"
        with open("sci_summary.txt", "r", encoding="utf-8") as f: summary_ko = f.read()
    else:
        print("❌ [오류] 업로드할 요약 파일(summary.txt)이 없습니다. Generate부터 다시 실행해주세요.")
        sys.exit(1)

    print(f"🚀 타겟 확인됨: [{prefix.upper()}] 카테고리를 업로드합니다.")

    access_token = os.getenv('INSTA_ACCESS_TOKEN')
    account_id = os.getenv('INSTA_USER_ID')
    user_name = "bomhi" 
    repo_name = "insta-automation" 
    
    container_ids = []
    for i in range(3):
        img_url = f"https://raw.githubusercontent.com/{user_name}/{repo_name}/main/images/{prefix}_slide_{i}.png?t={int(time.time())}"
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
        
        if os.path.exists("biz_summary.txt"): os.remove("biz_summary.txt")
        if os.path.exists("sci_summary.txt"): os.remove("sci_summary.txt")
        
        biz_data, sci_data = get_processed_news()
        
        if biz_data:
            create_slides(biz_data, "biz")
            # 파일을 '쓰기 모드(w)'로 확실하게 열어서 데이터를 덮어씁니다.
            with open("biz_summary.txt", "w", encoding="utf-8") as f: 
                f.write(biz_data['summary_ko'])
                f.flush()
            print("🟢 경제(Biz) 콘텐츠 생성 완료! (biz_summary.txt 저장됨)")
            
        if sci_data:
            create_slides(sci_data, "sci")
            with open("sci_summary.txt", "w", encoding="utf-8") as f: 
                f.write(sci_data['summary_ko'])
                f.flush()
            print("🔵 과학(Sci) 콘텐츠 생성 완료! (sci_summary.txt 저장됨)")
            
    elif mode == "--upload":
        upload_to_insta()

if __name__ == "__main__":
    main()
