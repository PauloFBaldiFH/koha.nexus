#!/usr/bin/env python3
"""Gera windows/msix/Assets/*.png, os ícones e blocos do pacote MSIX.

Fonte: a gota do KohaNexusLogo.png (1080 px, fundo transparente), redesenhada
com Lanczos em cada tamanho que o Windows pede, sem nunca ampliar a fonte.
O compilar_msix.ps1 só copia estes arquivos e confere os tamanhos; rode
`python3 windows/msix/gerar_assets.py` (Pillow) ao trocar o logotipo.
"""
import os

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'Assets')
SCALES = (100, 125, 150, 200, 400)
TARGETS = (16, 24, 32, 48, 256)

# Nome base: (largura, altura, fração da altura ocupada pela gota) em scale-100.
TILES = {
    'Square44x44Logo': (44, 44, 0.92),
    'StoreLogo': (50, 50, 0.92),
    'Square71x71Logo': (71, 71, 0.60),
    'Square150x150Logo': (150, 150, 0.56),
    'Wide310x150Logo': (310, 150, 0.56),
    'Square310x310Logo': (310, 310, 0.50),
}


def droplet():
    logo = Image.open(os.path.join(HERE, 'KohaNexusLogo.png')).convert('RGBA')
    # A gota fica acima do texto "koha": a primeira faixa de linhas não vazias.
    alpha = logo.getchannel('A')
    top = None
    for y in range(logo.height):
        filled = any(alpha.getpixel((x, y)) > 8 for x in range(0, logo.width, 2))
        if filled and top is None:
            top = y
        elif not filled and top is not None:
            band = logo.crop((0, top, logo.width, y))
            return band.crop(band.getbbox())
    raise SystemExit('KohaNexusLogo.png: gota não encontrada')


def render(mark, width, height, fraction):
    canvas = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    box = min(height * fraction, width * fraction, mark.height)
    ratio = min(box / mark.height, box / mark.width)
    size = (max(1, round(mark.width * ratio)), max(1, round(mark.height * ratio)))
    scaled = mark.resize(size, Image.LANCZOS)
    canvas.alpha_composite(scaled, ((width - size[0]) // 2, (height - size[1]) // 2))
    return canvas


def main():
    os.makedirs(OUT, exist_ok=True)
    for old in os.listdir(OUT):
        if old.endswith('.png'):
            os.remove(os.path.join(OUT, old))
    mark = droplet()
    files = []
    for name, (w, h, fraction) in TILES.items():
        for scale in SCALES:
            # Arredonda .5 para cima, como o Windows (71 x 150% = 107).
            sw, sh = int(w * scale / 100 + 0.5), int(h * scale / 100 + 0.5)
            files.append(('%s.scale-%d.png' % (name, scale), render(mark, sw, sh, fraction)))
    for size in TARGETS:
        icon = render(mark, size, size, 0.92 if size > 24 else 1.0)
        files.append(('Square44x44Logo.targetsize-%d.png' % size, icon))
        files.append(('Square44x44Logo.targetsize-%d_altform-unplated.png' % size, icon))
    for filename, image in files:
        image.save(os.path.join(OUT, filename), optimize=True)
    print('%d arquivos em %s' % (len(files), OUT))


if __name__ == '__main__':
    main()
