"""從 art/ 的原始美術產生安裝程式用的素材：uv run scripts/make_assets.py

  art/icon_source.png        → assets/icon.ico（16～256 多尺寸）、assets/icon.png（256，視窗左上角用）
  art/background_source.png  → assets/installer_bg.jpg（安裝程式背景，壓成 JPEG 讓 exe 小一點）

原始美術由 AI 生成（GPT 圖像），參考遊戲畫面的風格與配色。
"""

from pathlib import Path

from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
ART, ASSETS = ROOT / "art", ROOT / "assets"


def icon():
    src = Image.open(ART / "icon_source.png").convert("RGBA")
    if bbox := src.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox():
        src = src.crop(bbox)
    side = max(src.size)
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    square.paste(src, ((side - src.width) // 2, (side - src.height) // 2))
    sizes = [256, 128, 64, 48, 32, 24, 16]
    frames = []
    for s in sizes:
        im = square.resize((s, s), Image.LANCZOS)
        if s <= 32:  # 小尺寸稍微銳利化，輪廓才不會糊
            im = im.filter(ImageFilter.UnsharpMask(radius=0.8, percent=80, threshold=1))
        frames.append(im)
    frames[0].save(ASSETS / "icon.ico", sizes=[(s, s) for s in sizes], append_images=frames[1:])
    frames[0].save(ASSETS / "icon.png")


def background():
    bg = Image.open(ART / "background_source.png").convert("RGB")
    bg.save(ASSETS / "installer_bg.jpg", quality=90, optimize=True, progressive=True)


if __name__ == "__main__":
    icon()
    background()
    print("已產生 assets/icon.ico、icon.png、installer_bg.jpg")
