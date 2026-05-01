import os
import requests
import time
import sys
import textwrap
import re
import shutil
import json
import traceback
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
from bs4 import BeautifulSoup
_CACHED_MODEL = None

# [설정]
INSTA_ID = "@world_folio"

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
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

# [디버깅 패치: 에러 원인 상세 출력 및 가장 안정적인 최신 모델 다이렉트 꽂기]
# [최종 추적 패치: 구글의 허가 모델 리스트 강제 스캔 및 자동 매칭]
def analyze_and_generate_content(raw_text, category):
    global _CACHED_MODEL
    safe_text = raw_text[:5000]
    
    prompt = f"""
    [시스템 지시사항]
    당신은 100만 팔로워를 보유한 글로벌 프리미엄 뉴스 매거진의 '수석 편집장'이자 '카드뉴스 마케팅 최고 전문가'입니다.
    현재 당신이 다루는 기사의 카테고리는 [{category.upper()}] 입니다.

    [당신의 권한과 목표]
    1. 제공된 웹 텍스트(광고, 관련 기사 링크 등 노이즈 포함)에서 '단 하나의 가장 중요한 메인 스토리'만 완벽하게 발라내십시오.
    2. 기사의 성격(긴급한 경제 위기, 감동적인 휴먼 스토리, 경이로운 과학 발견 등)을 파악하여, 가장 몰입감 있고 세련된 톤앤매너로 자유롭게 글을 구성하십시오.
    3. 무조건 정중하고 전문적인 한국어 존댓말('~습니다', '~합니다')을 사용하십시오. 신문체('~다', '~이다')는 절대 금지합니다.

    [출력 형식: 반드시 아래 JSON 포맷만을 출력하십시오. 다른 부가 설명은 절대 금지합니다.]
    {{
        "ko_title": "15~25자 사이의 압도적인 헤드라인 (반드시 명사형으로 끝낼 것)",
        "hook_tag": "10자 내외의 시선을 끄는 상단 태그",
        "core_message": "카드뉴스 이미지 정중앙에 박힐 1~2문장의 가장 치명적이고 중요한 팩트 요약",
        "summary_ko": "인스타그램 본문에 들어갈 완벽한 캡션. (도입부, 스토리텔링, 통찰, 질문 포함. 적절한 이모지 사용)"
    }}

    [기사 원문]
    {safe_text}
    """

    for attempt in range(3):
        try:
            # 1. 내 API 키로 접속 가능한 모든 모델 리스트 강제 수거
            if not _CACHED_MODEL:
                models_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_API_KEY}"
                model_req = requests.get(models_url, timeout=10)
                model_req.raise_for_status()
                
                available_models = model_req.json().get('models', [])
                valid_models = [m.get('name') for m in available_models if 'generateContent' in m.get('supportedGenerationMethods', [])]
                
                print(f"\n👀 [비밀 장부 확보] 내 키로 쓸 수 있는 구글 AI 목록: {valid_models}", flush=True)
                
                # 1순위: 가장 빠르고 안정적인 gemini-1.5-flash 계열 (단, 테스트용 exp 제외)
                for name in valid_models:
                    if 'gemini-1.5-flash' in name and 'exp' not in name:
                        _CACHED_MODEL = name
                        break
                
                # 2순위: flash가 없으면 그냥 1.5 버전 아무거나
                if not _CACHED_MODEL:
                    for name in valid_models:
                        if 'gemini-1.5' in name:
                            _CACHED_MODEL = name
                            break
                            
                # 3순위: 그것도 없으면 리스트에 있는 첫 번째 제미나이 강제 할당
                if not _CACHED_MODEL:
                    for name in valid_models:
                        if 'gemini' in name:
                            _CACHED_MODEL = name
                            break
                            
                print(f"🎯 [타겟 설정] 최종 선택된 AI 모델: {_CACHED_MODEL}", flush=True)

            # 2. 선택된 모델로 다이렉트 통신
            url = f"https://generativelanguage.googleapis.com/v1beta/{_CACHED_MODEL}:generateContent?key={GEMINI_API_KEY}"
            
            headers = {'Content-Type': 'application/json'}
            data = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.4}
            }

            response = requests.post(url, headers=headers, json=data, timeout=30)
            
            if response.status_code == 429:
                print("\n🚫 [치명적 오류] 구글 API 할당량이 여전히 0이거나 초과되었습니다 (429 에러).", flush=True)
                sys.exit(1)

            response.raise_for_status() 
            
            res_json = response.json()
            ai_text = res_json['candidates'][0]['content']['parts'][0]['text']
            
            clean_str = ai_text.strip()
            if clean_str.startswith('```json'):
                clean_str = clean_str[7:-3].strip()
            elif clean_str.startswith('```'):
                clean_str = clean_str[3:-3].strip()
                
            return json.loads(clean_str)

        except Exception as e:
            if isinstance(e, SystemExit):
                raise e
                
            err_msg = str(e)
            if 'response' in locals() and hasattr(response, 'text'):
                err_msg += f" \n🔍 상세 내역: {response.text}"
                
            wait_time = (attempt + 1) * 10
            print(f"⚠️ API 통신 오류 발생: {err_msg}", flush=True)
            print(f"⏳ {wait_time}초 후 재시도합니다... (시도: {attempt+1}/3)", flush=True)
            time.sleep(wait_time)
            
    return None
def process_single_article(article_data, category):
    full_text = crawl_full_text(article_data['url'])
    if not full_text or len(full_text) < 300: return None

    print(f"⏳ Gemini 최신 엔진이 [{category.upper()}] 기사를 심층 분석 및 집필 중입니다...")
    ai_content = analyze_and_generate_content(full_text, category)
    
    if not ai_content: return None

    source_name = article_data['source']['name'] or "Global News"
    summary = f"📢 [{ai_content['ko_title']}]\n\n{ai_content['summary_ko']}"

    return {
        'ko_title': ai_content['ko_title'], 
        'core_message': ai_content['core_message'], 
        'hook_tag': ai_content['hook_tag'],        
        'summary_ko': summary, 
        'image_url': article_data.get('urlToImage'), 
        'source_name': source_name
    }

def get_processed_news():
    print("\n🔍 [1단계: 투트랙(경제/과학) 뉴스 동시 수집 중...]", flush=True)
    api_key = os.getenv('NEWS_API_KEY')
    
    if not api_key:
        print("❌ [오류] NEWS_API_KEY가 없습니다. 깃허브 시크릿을 확인하세요.", flush=True)
        return None, None

    b_url = f"https://newsapi.org/v2/top-headlines?country=us&category=business&pageSize=10&apiKey={api_key}"
    s_url = f"https://newsapi.org/v2/top-headlines?country=us&category=science&pageSize=10&apiKey={api_key}"
    
    biz_result = None
    sci_result = None
    
    try:
        # 1. 경제 뉴스 수집
        b_res = requests.get(b_url, timeout=15).json()
        if b_res.get('status') != 'ok':
            print(f"❌ [뉴스 API 거절 - BIZ] 사유: {b_res}", flush=True)
        else:
            for a in b_res.get('articles', []):
                if a.get('urlToImage') and a.get('url'):
                    biz_result = process_single_article(a, "biz")
                    if biz_result: 
                        print("⏱️ 서버 과부하 방지를 위해 15초간 대기합니다...", flush=True)
                        time.sleep(15)
                        break
                        
        # 2. 과학 뉴스 수집
        s_res = requests.get(s_url, timeout=15).json()
        if s_res.get('status') != 'ok':
            print(f"❌ [뉴스 API 거절 - SCI] 사유: {s_res}", flush=True)
        else:
            for a in s_res.get('articles', []):
                if a.get('urlToImage') and a.get('url'):
                    sci_result = process_single_article(a, "sci")
                    if sci_result: break
                    
    except Exception as e:
        print(f"❌ 뉴스 리스트 가져오기 실패 (타임아웃 등): {e}", flush=True)

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
        if not os.path.exists(font_path): font_path = "NanumSquareR.ttf"

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
            title_font = hook_font = core_font = id_font = source_font = cta_main_font = cta_sub_font = ImageFont.load_default()
            is_default_font = True

        try:
            resample_filter = Image.Resampling.LANCZOS
        except AttributeError:
            resample_filter = Image.LANCZOS

        anchor_val = None if is_default_font else "mm"

        # 1번 슬라이드
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

        # 2번 슬라이드
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

        # 3번 슬라이드
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

def upload_to_insta(prefix):
    print(f"\n📤 [3단계: 인스타그램 최종 게시 - 타겟: {prefix.upper()}]")
    
    summary_file = f"{prefix}_summary.txt"
    if not os.path.exists(summary_file):
        print(f"❌ [오류] {summary_file} 파일이 없습니다. Generate가 정상적으로 완료되었는지 확인하세요.")
        sys.exit(1)
        
    with open(summary_file, "r", encoding="utf-8") as f: 
        summary_ko = f.read()

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
        
        biz_data, sci_data = get_processed_news()
        
        if biz_data:
            create_slides(biz_data, "biz")
            with open("biz_summary.txt", "w", encoding="utf-8") as f: 
                f.write(biz_data['summary_ko'])
            print("\n" + "="*50)
            print("📰 [BIZ(경제) 미리보기]")
            print("="*50)
            print(biz_data['summary_ko'])
            print("="*50 + "\n")
            
        if sci_data:
            create_slides(sci_data, "sci")
            with open("sci_summary.txt", "w", encoding="utf-8") as f: 
                f.write(sci_data['summary_ko'])
            print("\n" + "="*50)
            print("📰 [SCI(과학) 미리보기]")
            print("="*50)
            print(sci_data['summary_ko'])
            print("="*50 + "\n")
            
    elif mode == "--upload":
        if len(sys.argv) < 3:
            print("❌ 업로드할 카테고리(biz 또는 sci)를 지정해주세요.")
            sys.exit(1)
        category = sys.argv[2]
        upload_to_insta(category)

if __name__ == "__main__":
    main()
