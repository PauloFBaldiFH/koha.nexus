#!/usr/bin/env python3
"""Gera o ícone próprio do Koha.Nexus e todos os arquivos que saem dele.

A Store recusou o 1.0.28.0 (10.1.1.11): os blocos usavam a gota verde do
logotipo do Koha, que é da comunidade Koha, e "os blocos não podem ter imagem
de um produto que não é seu". O símbolo agora é desenhado aqui, só com formas
geométricas: um livro aberto com uma rede de três nós em cima.

Saídas (rode `python3 windows/msix/gerar_assets.py`, com Pillow):
- KohaNexusMark.png: o símbolo em 1080 px, fundo transparente;
- KohaNexusIcon.ico: ícone do launcher, da janela e dos atalhos (16 a 256);
- Assets/*.png: blocos e ícones do pacote MSIX em todas as escalas;
- store-listing/*.png: imagens da página da loja (bloco 300x300, box art
  1080x1080 e pôster 720x1080).
O compilar_msix.ps1 só copia esses arquivos e confere os tamanhos.
"""
import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'Assets')
LISTING = os.path.join(HERE, 'store-listing')
SCALES = (100, 125, 150, 200, 400)
TARGETS = (16, 24, 32, 48, 256)
ICO_SIZES = (16, 20, 24, 32, 40, 48, 64, 96, 128, 256)

PAGE_LEFT = (13, 110, 120, 255)
PAGE_RIGHT = (20, 150, 160, 255)
NETWORK = (245, 166, 35, 255)
POSTER_BG = (12, 32, 38, 255)

# Nome base: (largura, altura, fração da altura ocupada pelo símbolo) em scale-100.
TILES = {
    'Square44x44Logo': (44, 44, 0.92),
    'StoreLogo': (50, 50, 0.92),
    'Square71x71Logo': (71, 71, 0.60),
    'Square150x150Logo': (150, 150, 0.56),
    'Wide310x150Logo': (310, 150, 0.56),
    'Square310x310Logo': (310, 310, 0.50),
}


def _curve(p0, p1, p2, steps=64):
    pts = []
    for i in range(steps + 1):
        t = i / steps
        pts.append(((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0],
                    (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1]))
    return pts


def mark():
    """O símbolo em 1080 px, desenhado em 2048 px e reduzido (bordas suaves)."""
    size = 2048
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    cx = size / 2
    for side, colour in ((-1, PAGE_LEFT), (1, PAGE_RIGHT)):
        spine = cx + side * 30
        edge = cx + side * (cx - 330)
        top = _curve((spine, 1020), (cx + side * 350, 760), (edge, 880))
        bottom = _curve((edge, 1560), (cx + side * 350, 1440), (spine, 1700))
        draw.polygon(top + bottom, fill=colour)
    nodes = [(cx, 330), (cx - 380, 690), (cx + 380, 690)]
    for a, b in ((0, 1), (0, 2), (1, 2)):
        draw.line([nodes[a], nodes[b]], fill=NETWORK, width=70)
    for x, y in nodes:
        draw.ellipse([x - 135, y - 135, x + 135, y + 135], fill=NETWORK)
    img = img.crop(img.getbbox())
    side = max(img.size)
    square = Image.new('RGBA', (side, side), (0, 0, 0, 0))
    square.paste(img, ((side - img.width) // 2, (side - img.height) // 2))
    return square.resize((1080, 1080), Image.LANCZOS)


def render(symbol, width, height, fraction, background=(0, 0, 0, 0)):
    canvas = Image.new('RGBA', (width, height), background)
    box = min(height * fraction, width * fraction, symbol.height)
    ratio = min(box / symbol.height, box / symbol.width)
    size = (max(1, round(symbol.width * ratio)), max(1, round(symbol.height * ratio)))
    scaled = symbol.resize(size, Image.LANCZOS)
    canvas.alpha_composite(scaled, ((width - size[0]) // 2, (height - size[1]) // 2))
    return canvas


def _font(px):
    for name in ('segoeuib.ttf', 'DejaVuSans-Bold.ttf', 'LiberationSans-Bold.ttf'):
        for folder in (os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts'),
                       '/usr/share/fonts/truetype/dejavu', '/usr/share/fonts/truetype/liberation'):
            path = os.path.join(folder, name)
            if os.path.exists(path):
                return ImageFont.truetype(path, px)
    raise SystemExit('Nenhuma fonte encontrada para o nome no pôster')


def listing(symbol):
    """Imagens da página da loja: o símbolo e o nome Koha.Nexus."""
    out = {'tile-300x300.png': render(symbol, 300, 300, 0.80)}
    for name, (w, h, fraction, title_y) in {
            'boxart-1080x1080.png': (1080, 1080, 0.50, 0.80),
            'poster-720x1080.png': (720, 1080, 0.55, 0.72)}.items():
        canvas = Image.new('RGBA', (w, h), POSTER_BG)
        box = int(min(w, h) * fraction)
        scaled = symbol.resize((box, box), Image.LANCZOS)
        canvas.alpha_composite(scaled, ((w - box) // 2, int(h * title_y) - box - int(h * 0.06)))
        draw = ImageDraw.Draw(canvas)
        font = _font(int(w * 0.11))
        text = 'Koha.Nexus'
        left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
        draw.text(((w - (right - left)) // 2 - left, int(h * title_y) - top), text, font=font, fill=(255, 255, 255, 255))
        out[name] = canvas
    return out


def main():
    symbol = mark()
    symbol.save(os.path.join(HERE, 'KohaNexusMark.png'), optimize=True)
    icon = render(symbol, 256, 256, 1.0)
    icon.save(os.path.join(HERE, 'KohaNexusIcon.ico'), sizes=[(s, s) for s in ICO_SIZES])

    os.makedirs(OUT, exist_ok=True)
    for old in os.listdir(OUT):
        if old.endswith('.png'):
            os.remove(os.path.join(OUT, old))
    files = []
    for name, (w, h, fraction) in TILES.items():
        for scale in SCALES:
            # Arredonda .5 para cima, como o Windows (71 x 150% = 107).
            sw, sh = int(w * scale / 100 + 0.5), int(h * scale / 100 + 0.5)
            files.append(('%s.scale-%d.png' % (name, scale), render(symbol, sw, sh, fraction)))
    for size in TARGETS:
        target = render(symbol, size, size, 0.92 if size > 24 else 1.0)
        files.append(('Square44x44Logo.targetsize-%d.png' % size, target))
        files.append(('Square44x44Logo.targetsize-%d_altform-unplated.png' % size, target))
    for filename, image in files:
        image.save(os.path.join(OUT, filename), optimize=True)

    os.makedirs(LISTING, exist_ok=True)
    for filename, image in listing(symbol).items():
        image.convert('RGB' if 'tile' not in filename else 'RGBA').save(os.path.join(LISTING, filename), optimize=True)
    print('%d arquivos em %s, ícone, símbolo e imagens da loja' % (len(files), OUT))


if __name__ == '__main__':
    main()
