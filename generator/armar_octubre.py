#!/usr/bin/env python3
"""Arma la página del festival del 24 de octubre a partir del PDF de la
programación, usando la página de julio como plantilla (estilos, barra del
club y buscador).

Uso: python3 generator/armar_octubre.py fixture.pdf 2026-julio/index.html index.html
"""
import re, sys, html
from collections import OrderedDict
import pdfplumber

pdf_path, plantilla_path, salida_path = sys.argv[1:4]

HORA = re.compile(r'^\d{1,2}:\d{2}$')
CANCHA = re.compile(r'CANCHA\s*(\d+)', re.I)


def norm(eq):
    eq = ' '.join((eq or '').split())
    # El PDF escribe "S.FRANCES" sin tilde en algunas filas de SUB 8
    eq = eq.replace('S.FRANCES', 'S.FRANCÉS')
    return eq


def etiqueta(catzona):
    """'S10 - Z A' -> ('SUB 10', 'Z A'); 'S10 DvsV' -> ('SUB 10', 'D vs V')."""
    c = ' '.join(catzona.split())
    m = re.match(r'S(\d+)\s*(.*)$', c)
    cat = 'SUB ' + m.group(1)
    resto = m.group(2).lstrip('- ').strip()
    if resto == 'DvsV':
        resto = 'D vs V'
    elif resto == 'VAR':
        resto = 'VAR'
    return cat, resto


# 1. Partidos por cancha ------------------------------------------------------
canchas = OrderedDict()   # numero -> lista de (hora, cat, zona, eq1, eq2) o (hora, 'RIEGO')
with pdfplumber.open(pdf_path) as pdf:
    for page in pdf.pages:
        for t in page.extract_tables():
            # Columna de inicio de cada bloque "Hora" y su cancha
            bloques = {}
            for fila in t:
                for ci, cel in enumerate(fila):
                    m = CANCHA.search(cel or '')
                    if m:
                        bloques[ci] = int(m.group(1))
            if not bloques:
                continue
            # La columna "Hora" de cada bloque: la cancha puede estar rotulada en col+1
            inicio = {}
            for fila in t:
                for ci, cel in enumerate(fila):
                    if (cel or '').strip() == 'Hora':
                        cerca = [c for c in bloques if c in (ci, ci + 1)]
                        if cerca:
                            inicio[ci] = bloques[cerca[0]]
            for fila in t:
                for ci, num in inicio.items():
                    hora = (fila[ci] or '').strip()
                    if not HORA.match(hora):
                        continue
                    cz, e1, e2 = (fila[ci + 1] or ''), norm(fila[ci + 2]), norm(fila[ci + 3])
                    lista = canchas.setdefault(num, [])
                    if 'RIEGO' in cz.upper() or 'RIEGO' in e1.upper():
                        lista.append((hora, 'RIEGO'))
                    elif cz.strip() and e1 and e2:
                        cat, zona = etiqueta(cz)
                        lista.append((hora, cat, zona, e1, e2))
                    # filas con hora y sin partido (bloques libres): se omiten

for n in canchas:
    canchas[n].sort(key=lambda x: x[0])

# Equipos de varones: los que juegan partidos "VAR" (varones contra varones).
# Sale de las etiquetas del PDF, no de que el nombre venga sin número.
VARONES = {}
for n in canchas:
    for p in canchas[n]:
        if p[1] != 'RIEGO' and p[2] == 'VAR':
            VARONES.setdefault(p[1], set()).update((p[3], p[4]))
for n in canchas:
    for p in canchas[n]:
        if p[1] != 'RIEGO' and p[2] == 'D vs V':
            assert sum(eq in VARONES.get(p[1], ()) for eq in (p[3], p[4])) == 1, p
# En la página se llaman "<CLUB> VARONES", para que no se confundan con las damas
SUFIJO_V = ' VARONES'
for n in canchas:
    canchas[n] = [p if p[1] == 'RIEGO' else
                  (p[0], p[1], p[2],
                   p[3] + SUFIJO_V if p[3] in VARONES.get(p[1], ()) else p[3],
                   p[4] + SUFIJO_V if p[4] in VARONES.get(p[1], ()) else p[4])
                  for p in canchas[n]]

# 2. Secciones ------------------------------------------------------------------
SECCIONES = [
    ('sub10', 'SUB 10', 'Sub 10 Damas y Varones', [1, 2, 3, 4],
     'Canchas 1 a 4. Damas y varones en canchas 1 y 2 (D vs V: damas contra varones); solo damas en 3 y 4. Los equipos de varones dicen VARONES.'),
    ('sub8', 'SUB 8', 'Sub 8 Damas y Varones', [5, 6, 7, 8, 9],
     'Canchas 5 a 9. Damas y varones en canchas 5 y 6; solo damas en 7, 8 y 9. Los equipos de varones dicen VARONES.'),
    ('sub6', 'SUB 6', 'Sub 6 Mixto', [10, 11], 'Canchas 10 y 11.'),
]
ZONA_TXT = {'D vs V': 'D vs V', 'VAR': 'Varones'}


def zonas_de(cat, nums):
    z = OrderedDict()
    for n in nums:
        for p in canchas.get(n, []):
            if p[1] == 'RIEGO' or p[1] != cat:
                continue
            clave = p[2] if p[2] not in ('D vs V', 'VAR') else 'VAR'
            s = z.setdefault(clave, [])
            for eq in (p[3], p[4]):
                # En "D vs V" solo el equipo de varones va a la zona "Varones"
                if p[2] == 'D vs V' and not eq.endswith(SUFIJO_V):
                    continue
                if eq not in s:
                    s.append(eq)
    return z


def orden_zona(k):
    return (1, '') if k == 'VAR' else (0, k)


def partidos_de(n):
    return [p for p in canchas.get(n, []) if p[1] != 'RIEGO']


out = ['<div class="prog-head"><h2>Programación completa</h2>'
       '<p class="cat-note">Toca una categoría para ver sus canchas. Si eliges tu equipo arriba, se abren solas.</p></div>', '']
for sid, cat, titulo, nums, nota in SECCIONES:
    total_cat = sum(len(partidos_de(n)) for n in nums)
    rango = f'Canchas {nums[0]} a {nums[-1]}' if len(nums) > 2 else f'Canchas {nums[0]} y {nums[-1]}'
    out.append(f'<section id="{sid}">')
    out.append(f'<details class="cat-d"><summary><h2>{html.escape(titulo)}</h2>'
               f'<span class="cat-m">{rango} · {total_cat} partidos</span></summary>')
    out.append('<div class="cat-body">')
    out.append(f'<p class="cat-note">{html.escape(nota)}</p>')
    zs = zonas_de(cat, nums)
    out.append(f'<details class="zonas-d"><summary>Ver zonas {cat}</summary><div class="zonas">')
    for k in sorted(zs, key=orden_zona):
        nombre = 'Varones' if k == 'VAR' else 'Zona ' + k.replace('Z ', '')
        out.append(f'<div class="zona"><b>{nombre}</b>{" · ".join(html.escape(e) for e in zs[k])}</div>')
    out.append('</div></details>')
    out.append('')
    for n in nums:
        ps = partidos_de(n)
        out.append(f'<details class="cancha" data-cancha="{n}"><summary><h3>Cancha {n}</h3>'
                   f'<span class="can-m">{len(ps)} partidos · {ps[0][0]} a {ps[-1][0]}</span></summary>')
        out.append('<table><tr><th>Hora</th><th>Zona</th><th>Equipo 1</th><th>Equipo 2</th></tr>')
        for p in canchas.get(n, []):
            if p[1] == 'RIEGO':
                out.append(f'<tr class="riego"><td colspan="4">{p[0]} — RIEGO</td></tr>')
                continue
            hora, c, zona, e1, e2 = p
            z = ZONA_TXT.get(zona, zona)
            out.append(f'<tr data-cat="{c}"><td class="h">{hora}</td><td class="z">{html.escape(z)}</td>'
                       f'<td>{html.escape(e1)}</td><td>{html.escape(e2)}</td></tr>')
        out.append('</table></details>')
        out.append('')
    out.append('</div></details>')
    out.append('</section>')
    out.append('')
secciones_html = '\n'.join(out)

def rep(s, a, b, n=1):
    assert s.count(a) == n, (a, s.count(a))
    return s.replace(a, b)


# 3. Plantilla de julio ---------------------------------------------------------
tpl = open(plantilla_path, encoding='utf-8').read()
# La firma se agrega una sola vez al final (si la plantilla ya la trae, se saca)
tpl = re.sub(r'<div class="firma-pie">.*?</style>\n', '', tpl, flags=re.S)
FIRMA = '<div class="firma-pie"><a class="firma-bianca" href="https://bianca-studios.vercel.app/?de=oldreds-festival" target="_blank" rel="noopener" title="Pregúntale a Remo"><img src="https://bianca-studios.vercel.app/firma/remo.webp" alt="" width="34" height="34" loading="lazy"><span><i>Sviluppato da</i> Bianca</span><span><i>Powered by</i> Remo</span></a></div>\n<style>.firma-bianca{display:inline-flex;align-items:center;gap:.55em;padding:.35em .55em .35em .35em;border:2px solid #0f0f12;border-radius:4px;background:repeating-linear-gradient(135deg,#cdb8ff 0 10px,#7fe8e0 10px 20px);box-shadow:3px 3px 0 #0f0f12;color:#0f0f12;text-decoration:none;font:600 13px/1.1 system-ui,-apple-system,"Segoe UI",sans-serif;letter-spacing:.01em}.firma-bianca:hover,.firma-bianca:focus-visible{translate:1px 1px;box-shadow:2px 2px 0 #0f0f12}.firma-bianca img{width:34px;height:34px;display:block;border:2px solid #0f0f12;border-radius:3px;background:#fff}.firma-bianca span{display:inline-block;padding:.3em .55em;border:2px solid #0f0f12;border-radius:3px;background:#fff;white-space:nowrap}.firma-bianca span+span{background:#ffa6d5}.firma-bianca i{font-style:normal;font-weight:400;opacity:.8}.firma-pie{display:flex;justify-content:center;padding:24px 16px}@media (prefers-reduced-motion:reduce){.firma-bianca:hover{translate:0}}</style>\n'

cabeza, resto = tpl.split('<div class="hero">', 1)
_, script = resto.split('<script>', 1)
script = '<script>' + script

cabeza = (cabeza
          .replace('<title>Festival Infantil · Old Reds · Sáb 25 Julio</title>',
                   '<title>Festival Infantil · Old Reds · Sáb 24 Octubre</title>')
          .replace('content="Festival Infantil Old Reds — Sáb 25 Julio"',
                   'content="Festival Infantil Old Reds — Sáb 24 Octubre"'))
# Vista previa al compartir (WhatsApp y otros): el escudo del club
OG = '''<meta property="og:image" content="https://oldreds-festival.vercel.app/assets/og-festival.jpg">
<meta property="og:image:type" content="image/jpeg">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="Escudo de Old Reds">
<meta property="og:site_name" content="Old Reds">
<meta name="twitter:card" content="summary_large_image">
<meta name="description" content="Festival Infantil Old Reds, sábado 24 de octubre en Cancha UC. Busca tu equipo y encuentra tus horarios y canchas.">
'''
cabeza = rep(cabeza, '<meta property="og:url" content="https://oldreds-festival.vercel.app">\n',
             '<meta property="og:url" content="https://oldreds-festival.vercel.app">\n' + OG)
cabeza = rep(cabeza, 'content="Programación SUB 10, SUB 8 y SUB 6. Busca tu equipo y encuentra tus horarios y canchas. Cancha UC."',
             'content="Sábado 24 de octubre, Cancha UC. Programación SUB 10, SUB 8 y SUB 6: busca tu equipo y encuentra tus horarios y canchas."')
# Mapa: 11 canchas en 5 columnas
cabeza = cabeza.replace(
    '.lgrid{display:grid;grid-template-columns:1fr 1fr 1fr 1fr 1.4fr;',
    '.lgrid{display:grid;grid-template-columns:1fr 1fr 1fr 1fr 1.4fr;')  # no-op guard
cabeza = cabeza.replace(
    '.lgrid{display:grid;grid-template-columns:1fr 1fr 1fr 1.4fr;gap:6px;',
    '.lgrid{display:grid;grid-template-columns:repeat(5,1fr);gap:6px;')
cabeza = cabeza.replace('.lc{border-radius:6px;padding:14px 4px;color:#fff}',
                        '.lc{border-radius:6px;padding:14px 2px;color:#fff;line-height:1.25}\n'
                        '.lx{font-size:10px;font-weight:600;color:var(--dim);text-align:center;padding:2px 0;letter-spacing:.3px}\n'
                        '.ausp{padding-top:14px}\n'
                        '.prog-head{max-width:640px;margin:0 auto;padding:22px 12px 0}\n'
                        '.prog-head h2{margin-bottom:4px}\n'
                        '.prog-head .cat-note{margin-left:14px;margin-bottom:0}\n'
                        'section{padding:10px 12px}\n'
                        'details.cat-d,details.cancha{background:transparent;border:0;margin:0;border-radius:0}\n'
                        'details.cat-d>summary{list-style:none;display:flex;flex-wrap:wrap;align-items:center;gap:4px 12px;padding:8px 34px 8px 0;position:relative}\n'
                        'details.cat-d>summary h2{margin:0}\n'
                        '.cat-m{font-family:var(--or-mono);font-size:12px;color:var(--ink);font-variant-numeric:tabular-nums}\n'
                        'details>summary::-webkit-details-marker{display:none}\n'
                        'details.cat-d>summary::after,details.cancha>summary::after{content:"";position:absolute;right:12px;top:50%;width:9px;height:9px;border-right:2px solid currentColor;border-bottom:2px solid currentColor;transform:translateY(-70%) rotate(45deg);transition:transform .15s}\n'
                        'details[open].cat-d>summary::after,details[open].cancha>summary::after{transform:translateY(-30%) rotate(-135deg)}\n'
                        '.cat-body{padding-top:4px}\n'
                        'details.cancha{margin-top:10px}\n'
                        'details.cancha>summary{list-style:none;padding:0;position:relative;display:flex;align-items:center;gap:10px;background:var(--dark);color:#fff;border-radius:8px}\n'
                        'details[open].cancha>summary{border-radius:8px 8px 0 0}\n'
                        'details.cancha>summary h3{margin:0;background:none;padding:10px 0 10px 12px}\n'
                        '.can-m{font-family:var(--or-mono);font-size:11px;color:#d8d0cc;font-variant-numeric:tabular-nums;padding-right:34px}\n'
                        'details.cat-d>summary:focus-visible,details.cancha>summary:focus-visible{outline:3px solid var(--red);outline-offset:2px}\n'
                        '@media (prefers-reduced-motion:reduce){details>summary::after{transition:none}}\n'
                        ':root{--aviso-bg:#fff8e6;--aviso-borde:#ecd9a6;--aviso-texto:var(--or-paper-ink)}\n'
                        '.aviso-llegada{max-width:640px;margin:12px auto 0;padding:0 12px}\n'
                        '.aviso-llegada p{background:var(--aviso-bg);border:1px solid var(--aviso-borde);border-radius:8px;padding:10px 12px;font-size:14px;line-height:1.4;color:var(--aviso-texto)}\n'
                        '.mis-llega{padding:10px 14px;background:var(--aviso-bg);border-bottom:1px solid var(--aviso-borde);font-size:14px;line-height:1.4;color:var(--aviso-texto)}\n'
                        '.mis-llega b{font-variant-numeric:tabular-nums}\n'
                        '.mis-sep .llega{font-size:12px;font-weight:600;text-transform:none;letter-spacing:0;margin-left:8px;color:var(--aviso-texto);font-variant-numeric:tabular-nums}\n'
                        '.ausp-t{font-family:var(--or-mono);font-size:var(--or-label-size);letter-spacing:var(--or-label-track);text-transform:uppercase;color:var(--ink);margin-bottom:8px}\n'
                        '.ausp-l{list-style:none;display:grid;grid-template-columns:repeat(3,1fr);gap:8px}\n'
                        '.ausp-l li{background:var(--or-paper-surface);border:1px solid var(--line);border-radius:8px;display:flex;align-items:center;justify-content:center;padding:12px 10px;min-height:84px}\n'
                        '.ausp-l img{display:block;max-width:100%;width:auto}')

medio = '''<div class="hero">
''' + re.search(r'<div class="hero">\n(<img [^\n]*>)', tpl).group(1) + '''
<h1>Festival Infantil</h1>
<p>SUB 10 · SUB 8 · SUB 6 — Sábado 24 de octubre · Cancha UC · Old Reds</p>
</div>

<div class="aviso-llegada"><p><b>Llega 30 minutos antes de tu primer partido.</b> Este sábado hay atletismo en San Carlos de Apoquindo: evita el taco.</p></div>

<div class="finder">
<div class="finder-card">
<div class="fc-title">Encuentra a tu equipo</div>
<p class="fc-sub">Elige categoría y equipo: verás tus horarios y tu cancha marcada en el mapa.</p>
<label for="selCat">Categoría</label>
<select id="selCat"><option value="">— Elegir categoría —</option></select>
<label for="selTeam">Equipo</label>
<select id="selTeam" disabled><option value="">— Primero elige categoría —</option></select>
</div>
<div class="mis" id="misCard">
<div class="mis-head" id="misHead"></div>
<div id="misList"></div>
<div class="mis-map">📍 Tus canchas están destacadas en el mapa de abajo.</div>
<button class="share-btn" id="shareBtn">📤 Compartir programación</button>
</div>
<details class="finder-map">
<summary>📍 Mapa de canchas</summary>
<div class="lgrid" id="layout">
<div class="lx" style="grid-area:1/3/2/5">Banca de suplentes</div>
<div class="lc lb" style="grid-area:2/1">CANCHA<br>11</div><div class="lc lb" style="grid-area:2/2">CANCHA<br>8</div><div class="lc lb" style="grid-area:2/3">CANCHA<br>7</div><div class="lc lb" style="grid-area:2/4">CANCHA<br>6</div><div class="lc lb" style="grid-area:2/5">CANCHA<br>5</div>
<div class="lc lb" style="grid-area:3/1">CANCHA<br>10</div><div class="lc lg" style="grid-area:3/2/4/4">CANCHA 2</div><div class="lc lg" style="grid-area:3/4/4/6">CANCHA 4</div>
<div class="lc lb" style="grid-area:4/1">CANCHA<br>9</div><div class="lc lg" style="grid-area:4/2/5/4">CANCHA 1</div><div class="lc lg" style="grid-area:4/4/5/6">CANCHA 3</div>
<div class="lx" style="grid-area:5/4/6/6">Graderías</div>
</div>
<p class="lnote">Banca de suplentes junto a canchas 7 y 6 · Graderías frente a cancha 3</p>
</details>
<details class="finder-fair">
<summary><svg style="width:16px;height:16px;vertical-align:-2px;margin-right:4px" viewBox="0 0 24 24" fill="#C1291F"><path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/></svg> Presencia Positiva</summary>
<div class="fair-body">
<p class="fair-intro">Hoy es día de festival. Recordemos 3 cosas clave en la barra:</p>
<ul class="fair-list">
<li><strong>Aliento positivo</strong> para nuestros niños y niñas, y para el equipo rival.</li>
<li><strong>Respeto total</strong> a árbitros y rivales. Somos ejemplo.</li>
<li><strong>Disfrutar.</strong> Que sientan nuestro orgullo jugando.</li>
</ul>
<p class="fair-cta">¡A alentar!</p>
</div>
</details>
</div>

<section class="ausp" aria-label="Auspiciadores del festival">
<p class="ausp-t">Auspician</p>
<ul class="ausp-l">
<li><img src="assets/auspiciadores/bruno-fritsch.jpg" alt="Bruno Fritsch" width="400" height="53" style="height:20px"></li>
<li><img src="assets/auspiciadores/kastor.jpg" alt="Kastor" width="614" height="160" style="height:26px"></li>
<li><img src="assets/auspiciadores/receta-del-abuelo.jpg" alt="Receta del Abuelo" width="173" height="160" style="height:58px"></li>
</ul>
</section>

'''

pie = '''<footer>
Old Reds Hockey · Festival Infantil 24/10 · Cancha UC</footer>
'''

# 4. Ajustes al script ----------------------------------------------------------

script = rep(script,
    "var TC={'O.REDS':'#CD5241','COGS':'#1a5276','S.FRANCÉS':'#2471a3','MANQ':'#28b463','ALERCES':'#1e8449','S.ITALIANO':'#45b39d','PIONEROS CH':'#7d3c98','SJCH':'#e67e22','MACCABI':'#d4ac0d','O.GABS':'#5dade2'};",
    "var TC={'O.REDS':'#C1291F','COGS':'#1a5276','S.FRANCÉS':'#2471a3','U.CATÓLICA':'#1f4e9c','ALUMNI':'#28b463','DUNNERS':'#6c3483','BRITISH':'#7b241c','ÁGUILAS':'#b9770e','ALL BRADS':'#117a65','O.LOCKS':'#d4ac0d','ALERCES':'#1e8449','O.EAGLES':'#e67e22','PIONEROS':'#7d3c98','PELTRUN':'#45b39d','O.GABS':'#5dade2'};")
# Partidos: la categoría sale de cada fila (data-cat); canchas de dos dígitos
script = rep(script,
    "    var m=h.textContent.match(/Cancha\\s+(\\d)/i);",
    "    var m=h.textContent.match(/Cancha\\s+(\\d+)/i);")
script = rep(script,
    """      var cat;
      if(sec.id==='sub10') cat='SUB 10';
      else if(sec.id==='sub8') cat='SUB 8';
      else cat=(td[1].textContent.trim().indexOf('SUB 6')===0)?'SUB 6':'SUB 8';
""",
    """      var cat=tr.getAttribute('data-cat');
""")
script = rep(script, "    var sec=h.closest('section');\n", "")
script = rep(script, "var mm=c.textContent.match(/CANCHA\\s+(\\d)/);", "var mm=c.textContent.match(/CANCHA\\s*(\\d+)/);", 3)
script = rep(script, "function badgeClass(n){return (n==='1'||n==='2'||n==='3')?'g':'b';}",
             "function badgeClass(n){return (+n<=4)?'g':'b';}")
script = rep(script, "return d.getMonth()===6&&(d.getDate()===24||d.getDate()===25);",
             "return d.getMonth()===9&&d.getDate()===24;")
# Por horario: ordenar canchas como números (10 y 11 después de 9)
script = rep(script, "mine.sort(function(a,b){return a.cancha<b.cancha?-1:1;});",
             "mine.sort(function(a,b){return a.cancha-b.cancha;});")
script = rep(script, "'#141414'", "'var(--or-ink)'")
script = rep(script, "Festival Old Reds, Sáb 25 Jul, Cancha UC", "Festival Old Reds, Sáb 24 Oct, Cancha UC")
# Varones: el club agrupa sin el sufijo, y el buscador tiene "SUB 10 VARONES", etc.
script = rep(script, "function clubOf(name){var m=name.match(",
             "function clubOf(name){var m=name.replace(/ VARONES$/,'').match(")
cats_js = []
for c in ['SUB 10', 'SUB 8', 'SUB 6']:
    cats_js.append(c)
    if VARONES.get(c):
        cats_js.append(c + SUFIJO_V)
script = rep(script, "var CATS=['SUB 10','SUB 8','SUB 6'];",
             "var CATS=" + repr(cats_js).replace("'", "'") + ";\n"
             "  // 'SUB 10 VARONES' filtra los equipos de varones de SUB 10\n"
             "  function baseCat(v){return v.replace(/ VARONES$/,'');}\n"
             "  function itemsFor(v){var t=teamsFor(baseCat(v));return v===baseCat(v)?t:t.filter(function(x){return / VARONES$/.test(x);});}")
script = rep(script, "var items=(selCat.value==='CLUB')?allClubs():teamsFor(selCat.value);",
             "var items=(selCat.value==='CLUB')?allClubs():itemsFor(selCat.value);")
script = rep(script, "else apply(selCat.value,selTeam.value);", "else apply(baseCat(selCat.value),selTeam.value);", 2)
# Hora de llegada: 30 minutos antes del primer partido
script = rep(script, "function toMins(h){var p=h.split(':');return parseInt(p[0])*60+parseInt(p[1]);}",
             "function toMins(h){var p=h.split(':');return parseInt(p[0])*60+parseInt(p[1]);}\n"
             "  var ANTICIPO=30;\n"
             "  function llegada(lista){var m=Math.min.apply(null,lista.map(function(x){return toMins(x.hora);}))-ANTICIPO;"
             "var hh=Math.floor(m/60),mm=m%60;return (hh<10?'0':'')+hh+':'+(mm<10?'0':'')+mm;}")
script = rep(script, "    misHead.style.background=tColor(team);\n    misList.innerHTML='';\n",
             "    misHead.style.background=tColor(team);\n    misList.innerHTML='';\n"
             "    var av=document.createElement('div');av.className='mis-llega';\n"
             "    av.innerHTML='Llega a las <b>'+llegada(mine)+'</b>: 30 minutos antes de tu primer partido.';\n"
             "    misList.appendChild(av);\n")
script = rep(script, "      sep.innerHTML=grp.name;",
             "      sep.innerHTML=grp.name+'<span class=\"llega\">llega '+llegada(grp.matches)+'</span>';")
# Canchas en <details>: la tabla ya no sigue al h3
script = rep(script, """  document.querySelectorAll('h3').forEach(function(h){
    var m=h.textContent.match(/Cancha\\s+(\\d+)/i);
    if(!m) return;
    var cancha=m[1];
    var table=h.nextElementSibling;
    if(!table||table.tagName!=='TABLE') return;""", """  document.querySelectorAll('details.cancha').forEach(function(d){
    var cancha=d.getAttribute('data-cancha');
    var table=d.querySelector('table');
    if(!table) return;""")
# Al elegir un equipo se abren su categoría y sus canchas; al limpiar se cierran
script = rep(script, "  function openMap(){",
             "  var abiertos=[];\n"
             "  function abrir(tr){var c=tr.closest('details.cancha'),k=tr.closest('details.cat-d');"
             "[k,c].forEach(function(d){if(d&&!d.open){d.open=true;abiertos.push(d);}});}\n"
             "  function cerrarAbiertos(){abiertos.forEach(function(d){d.open=false;});abiertos=[];}\n"
             "  function openMap(){")
script = rep(script, "  function clearAll(){\n", "  function clearAll(){\n    cerrarAbiertos();\n")
script = rep(script, "      x.row.classList.add('mine');\n      var rival=(x.eq1===team)?x.eq2:x.eq1;",
             "      x.row.classList.add('mine');abrir(x.row);\n      var rival=(x.eq1===team)?x.eq2:x.eq1;")
# Sin links a las otras páginas de Old Reds: el festival se sostiene solo
cabeza = rep(cabeza, '<a class="or-brand" href="https://oldreds.vercel.app" aria-label="Ir al sitio de Old Reds">',
             '<div class="or-brand">')
cabeza = rep(cabeza, '<span class="or-ctx">Festival infantil</span></span>\n</a>',
             '<span class="or-ctx">Festival infantil</span></span>\n</div>')
cabeza = re.sub(r'<div class="or-push or-links">.*?</span>\n</div>\n', '', cabeza, count=1, flags=re.S)
assert 'oldreds-app.vercel.app' not in cabeza and 'href="https://oldreds.vercel.app"' not in cabeza
# Orden alfabético en español (ÁGUILAS junto a ALUMNI, no al final)
script = rep(script, "    return Object.keys(s).sort();\n",
             "    return Object.keys(s).sort(function(a,b){return a.localeCompare(b,'es',{numeric:true});});\n", 2)
# El huevo de pascua de COGS 2 era del equipo de julio: se saca hasta confirmar
script = re.sub(r"  // Easter 2:.*?\n  \};\n\n", "", script, flags=re.S)
assert 'Juega la Lau' not in script

script = rep(script, '</body>', FIRMA + '</body>')
open(salida_path, 'w', encoding='utf-8').write(cabeza + medio + secciones_html + pie + script)

total = sum(1 for n in canchas for p in canchas[n] if p[1] != 'RIEGO')
print('canchas:', {n: sum(1 for p in canchas[n] if p[1] != 'RIEGO') for n in canchas})
print('partidos:', total)
