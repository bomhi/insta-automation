import os
from PIL import Image, ImageDraw

def create_card():
    # 1080x1080 배경 생성
    img = Image.new('RGB', (1080, 1080), color=(73, 80, 243))
    draw = ImageDraw.Draw(img)
    
    # 텍스트 그리기 (폰트 파일 없이 기본 폰트 사용)
    draw.text((400, 500), "Automation Start!", fill=(255, 255, 255))

    if not os.path.exists("images"):
        os.makedirs("images")
    img.save("images/result.png")
    print("Image Created!")

if __name__ == "__main__":
    create_card()
