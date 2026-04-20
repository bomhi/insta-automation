import os
import requests
import time
import sys
import textwrap
import re
import shutil
import json
import traceback
import google.generativeai as genai
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
from bs4 import BeautifulSoup

# [설정]
INSTA_ID = "@world_folio"

# Gemini API 세팅
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
else:
    print("❌ GEMINI_API_KEY가 설정되지 않았습니다. GitHub Secrets를 확인해주세요.")
    sys.exit(1)

def is_valid_paragraph(text):
    text = text.strip()
    if len(text) < 40: return False
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

# =====================================================================
# 🧠 [초지능 코어] Gemini 1.5 Pro 수석 편집장 에이전트
# =====================================================================
def analyze_and_generate_content(raw_text, category):
    """
    Gemini 1.5 Pro를 사용하여 기사의 노이즈를 걸러내고, 
    최고의 카드뉴스용 헤드라인, 훅, 핵심 요약, 캡션을 한 번에 JSON 형태로 뽑아냅니다.
    """
    # 안전장치: 너무 긴 텍스트는 자름
    safe_text = raw_text[:5000]
    
    # 100만 팔로워 전문가 페르소나 및 자율권(Autonomy) 부여 프롬프트
    system_instruction = f"""
    당신은 100만 팔로워를 보유한 글로벌 프리미엄 뉴스 매거진의 '수석 편집장'이자 '카드뉴스 마케팅 최고 전문가'입니다.
    현재 당신이 다루는 기사의 카테고리는 [{category.upper()}] 입니다.

    [당신의 권한과 목표]
    1. 당신은 제공된 거친 웹 텍스트(광고, 관련 기사 링크 등 노이즈 포함)에서 '단 하나의 가장 중요한 메인 스토리'만 완벽하게 발라낼 수 있는 권한과 능력이 있습니다.
    2. 과거의 기계적인 3문단 규칙이나 하드코딩된 템플릿에 얽매일 필요 없습니다. 기사의 성격(긴급한 경제 위기, 감동적인 휴먼 스토리, 경이로운 과학 발견 등)을 스스로 판단하여, 가장 몰입감 있고 세련된 톤앤매너로 자유롭게 글을 구성하십시오.
    3. 단, 프리미엄 매거진의 품격을 위해 무조건 정중하고 전문적인 한국어 존댓말('~습니다', '~합니다')을 사용하십시오. 신문체('~다', '~이다')는 절대 금지합니다.

    [출력 형식: 반드시 아래 JSON 포맷만을 출력하십시오]
    {{
        "ko_title": "15~25자 사이의 압도적인 헤드라인 (반드시 명사형으로 끝낼 것. 예: 급락, 성취, 발견)",
        "hook_tag": "10자 내외의 시선을 끄는 상단 태그 (예: GLOBAL ECONOMY, TECH INSIGHT, HUMAN STORY)",
        "core_message": "카드뉴스 이미지 정중앙에 박힐 1~2문장의 가장 치명적이고 중요한 팩트 요약",
        "summary_ko": "인스타그램 본문에 들어갈 완벽한 캡션. (도입부, 스토리텔링, 통찰력 있는 결론, 독자의 댓글을 유도하는 질문 포함. 적절한 이모지 사용)"
    }}
    """

    model = genai.GenerativeModel(
        model_name="gemini-1.5-pro",
        system_instruction=system_instruction
    )

    try:
        response = model.generate_content(
            f"다음 웹 스크래핑 텍스트를 분석하여 완벽한 인스타그램 포스트용 JSON 데이터를 생성하십시오:\n\n{safe_text}",
            generation_config=genai.types.GenerationConfig(
                response_mime_type="application/json",
                temperature=0.4 # 창의성과 팩트의 균형
            )
        )
        
        # JSON 파싱
        result_json = json.loads(response.text)
        return result_json

    except Exception as e:
        print(f"❌ Gemini API 통신 오류: {e}")
        return None

def process_single_article(article_data, category):
    full_text = crawl_full_text(article_data['url'])
    if not full_text or len(full_text) < 300: return None

    # Gemini 편집장에게 원문 전달 및 완벽한 결과물(JSON) 수령
    print(f"⏳ Gemini 1.5 Pro가 [{category.upper()}] 기사를 심층 분석 및 집필 중입니다...")
    ai_content = analyze_and_generate_content(full_text, category)
    
    if not ai_content:
        return None

    source_name = article_data['source']['name'] or "Global News"

    # Gemini가 알아서 다 만들어준 완벽한 캡션 포장
    summary = f"📢 [{ai_content['ko_title']}]\n\n"
    summary += ai_content['summary_ko']

    return {
        'ko_title': ai_content['ko_title'], 
        'core_message': ai_content['core_message'], 
        'hook_tag': ai_content['hook_tag'],        
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
                biz_result = process_single_article(a, "biz")
                if biz_result: break
                
        s_res = requests.get(s_url).json()
        for a in s_res.get('articles', []):
            if a.get('urlToImage') and a.get('url'):
                sci_result = process_single_article(a, "sci")
                if sci_result: break
    except Exception as e:
        print(f"❌ 뉴스 리스트 가져오기 실패: {e}")

    return biz_result, sci_result

def create_slides(article, prefix):
    print(f"\n🎨 [2단계: {prefix.upper()} 슬라이드 3장 제작 중...]")
    width, height = 1080, 1080
    
    try:
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            orig_res = requests.get(article['image_url'], headers=headers, stream=True, timeout=10)
            orig_res.raise_for_status()
            raw_img = Image.open(orig_res.raw).convert('RGB')
        except:
            raw_img = Image.new('RGB', (width, height), color=(35, 40, 45))

        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        font_path = os.path.join(base_dir, "NanumSquareR.ttf")
        if not os.path.exists(font_path):
            font_path = "NanumSquareR.ttf"

        is_default_font = False
        try:
            title_font = ImageFont.truetype(font_path, 80) 
            hook_font = ImageFont.truetype(font_path, 35)   
            core_font = ImageFont.truetype(font_path, 40)   
            id_font = ImageFont.truetype(font_path, 28)
            source_font = ImageFont.truetype(font_path, 22)
            cta_main_font = ImageFont.truetype(font_path, 55)
            cta_sub_font = ImageFont.truetype(font_path, 40)
        except Exception as e:
            print(f"⚠️ 폰트 경고: {e} - 기본 폰트로 안전하게 대체합니다.")
            title_font = hook_font = core_font = id_font = source_font = cta_main_font = cta_sub_font = ImageFont.load_default()
            is_default_font = True

        try:
            resample_filter = Image.Resampling.LANCZOS
        except AttributeError:
            resample_filter = Image.LANCZOS

        anchor_val = None if is_default_font else "mm"

        # --- 1번 슬라이드 ---
        s1 = raw_img.copy().resize((width, height), resample_filter).filter(ImageFilter.GaussianBlur(radius=10))
        s1 = ImageEnhance.Brightness(s1).enhance(0.35) 
        draw = ImageDraw.Draw(s1)
        
        draw.text((width - 60, 60), INSTA_ID, fill=(255, 255, 255, 180), font=id_font, anchor="ra" if not is_default_font else None)
        draw.text((width//2, 180), article['hook_tag'], fill=(255, 225, 50), font=hook_font, anchor=anchor_val)
        
        wrapped_title = textwrap.fill(article['ko_title'], width=12)
        try:
            bbox_t = draw.multiline_textbbox((0, 0), wrapped_title, font=title_font, spacing=25)
            tw, th = bbox_t[2] - bbox_t[0], bbox_t[3] - bbox_t[1]
        except AttributeError:
            tw, th = draw.multiline_textsize(wrapped_title, font=title_font, spacing=25)
            
        draw.multiline_text(((width - tw)//2, (height//2 + 20) - (th//2)), wrapped_title, fill=(255, 255, 255), font=title_font, align="center", spacing=25)
        
        draw.text((width - 60, height - 60), f"Source: {article['source_name']}", fill=(255, 255, 255, 120), font=source_font, anchor="rd" if not is_default_font else None)
        s1.save(f"images/{prefix}_slide_0.png")

        # --- 2번 슬라이드 ---
        s2 = raw_img.copy().resize((width, height), resample_filter) 
        overlay = Image.new('RGBA', s2.size, (0, 0, 0, 0))
        draw_overlay = ImageDraw.Draw(overlay)
        
        start_y = int(height * 0.40)
        for y in range(start_y, height):
            alpha = int(255 * ((y - start_y) / (height - start_y)))
            draw_overlay.line([(0, y), (width, y)], fill=(0, 0, 0, alpha))
        
        wrapped_core = textwrap.fill(article['core_message'], width=24)
        try:
            bbox_c = draw_overlay.multiline_textbbox((0, 0), wrapped_core, font=core_font, spacing=15)
            cw, ch = bbox_c[2] - bbox_c[0], bbox_c[3] - bbox_c[1]
        except AttributeError:
            cw, ch = draw_overlay.multiline_textsize(wrapped_core, font=core_font, spacing=15)
            
        draw_overlay.multiline_text(((width - cw)//2, height - 120 - ch), wrapped_core, fill=(255, 255, 255, 250), font=core_font, align="center", spacing=15)
        
        s2 = Image.alpha_composite(s2.convert('RGBA'), overlay).convert('RGB')
        s2.save(f"images/{prefix}_slide_1.png")

        # --- 3번 슬라이드 ---
        s3 = Image.new('RGB', (width, height), color=(255, 255, 255))
        draw_s3 = ImageDraw.Draw(s3)
        
        pastel_color = (120, 150, 180) 
        draw_s3.text((width//2, 400), "오늘의 브리핑이 유익하셨나요?", fill=pastel_color, font=cta_main_font, anchor=anchor_val)
        draw_s3.text((width//2, 530), "좋아요  ·  댓글  ·  저장", fill=(180, 180, 180), font=cta_sub_font, anchor=anchor_val)
        draw_s3.text((width//2, 700), f"{INSTA_ID} 팔로우하기", fill=pastel_color, font=cta_sub_font, anchor=anchor_val)

        s3.save(f"images/{prefix}_slide_2.png")
        print(f"✅ [{prefix.upper()}] 슬라이드 생성 완료!")

    except Exception as e:
        print(f"\n❌ [치명적 오류] 이미지 렌더링 중 크래시 발생: {e}")
        traceback.print_exc()
        sys.exit(1)

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
