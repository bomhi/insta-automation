import os
import requests
from PIL import Image, ImageDraw, ImageFont

def create_card():
    # 1. 배경 이미지 생성 (예쁜 보라색 그라데이션 느낌)
    width, height = 1080, 1080
    img = Image.new('RGB', (width, height), color=(100, 50, 255))
    draw = ImageDraw.Draw(img)
    
    # 2. 텍스트 넣기 (크고 아름답게)
    # 글꼴이 없다면 기본 글꼴을 사용합니다.
    text = "오늘의 자동화 성공!\nGitHub Actions 완료"
    
    # 텍스트를 중앙에 배치하기 위한 설정
    # (폰트 파일이 저장소에 있다면 그 경로를 적어주세요. 없으면 기본 폰트 사용)
    try:
        # NanumSquareR.ttf 파일이 저장소 루트에 있다면 아래 코드가 작동합니다.
        font = ImageFont.truetype("NanumSquareR.ttf", 80)
    except:
        font = ImageFont.load_default()

    # 텍스트 그리기 (하얀색, 중앙 정렬 느낌)
    draw.text((width//2, height//2), text, fill=(255, 255, 255), anchor="mm", align="center")
    
    if not os.path.exists("images"):
        os.makedirs("images")
    img.save("images/result.png")
    print("새로운 디자인 이미지 생성 완료")

# ... (아래 upload_to_instagram 함수는 기존과 동일하게 유지)
