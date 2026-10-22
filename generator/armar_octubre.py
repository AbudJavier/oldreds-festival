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

# 2. Secciones ------------------------------------------------------------------
SECCIONES = [
    ('sub10', 'SUB 10', 'Sub 10 Damas y Varones', [1, 2, 3, 4],
     'Canchas 1 a 4. Damas y varones en canchas 1 y 2 (D vs V: damas contra varones); solo damas en 3 y 4.'),
    ('sub8', 'SUB 8', 'Sub 8 Damas y Varones', [5, 6, 7, 8, 9],
     'Canchas 5 a 9. Damas y varones en canchas 5 y 6; solo damas en 7, 8 y 9.'),
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
                # En "D vs V" el equipo con número es de damas: no va a "Varones"
                if p[2] == 'D vs V' and re.search(r'\d$', eq):
                    continue
                if eq not in s:
                    s.append(eq)
    return z


def orden_zona(k):
    return (1, '') if k == 'VAR' else (0, k)


out = []
for sid, cat, titulo, nums, nota in SECCIONES:
    out.append(f'<section id="{sid}">')
    out.append(f'<h2>{html.escape(titulo)}</h2>')
    out.append(f'<p class="cat-note">{html.escape(nota)}</p>')
    zs = zonas_de(cat, nums)
    out.append(f'<details><summary>Ver zonas {cat}</summary><div class="zonas">')
    for k in sorted(zs, key=orden_zona):
        nombre = 'Varones' if k == 'VAR' else 'Zona ' + k.replace('Z ', '')
        out.append(f'<div class="zona"><b>{nombre}</b>{" · ".join(html.escape(e) for e in zs[k])}</div>')
    out.append('</div></details>')
    out.append('')
    for n in nums:
        out.append(f'<h3>Cancha {n}</h3>')
        out.append('<table><tr><th>Hora</th><th>Zona</th><th>Equipo 1</th><th>Equipo 2</th></tr>')
        for p in canchas.get(n, []):
            if p[1] == 'RIEGO':
                out.append(f'<tr class="riego"><td colspan="4">{p[0]} — RIEGO</td></tr>')
                continue
            hora, c, zona, e1, e2 = p
            z = ZONA_TXT.get(zona, zona)
            out.append(f'<tr data-cat="{c}"><td class="h">{hora}</td><td class="z">{html.escape(z)}</td>'
                       f'<td>{html.escape(e1)}</td><td>{html.escape(e2)}</td></tr>')
        out.append('</table>')
        out.append('')
    out.append('</section>')
    out.append('')
secciones_html = '\n'.join(out)

# 3. Plantilla de julio ---------------------------------------------------------
tpl = open(plantilla_path, encoding='utf-8').read()
# Sin la firma agregada al final (cambio sin commit, pendiente de decidir)
tpl = re.sub(r'<div class="firma-pie">.*?</style>\n', '', tpl, flags=re.S)

cabeza, resto = tpl.split('<div class="hero">', 1)
_, script = resto.split('<script>', 1)
script = '<script>' + script

cabeza = (cabeza
          .replace('<title>Festival Infantil · Old Reds · Sáb 25 Julio</title>',
                   '<title>Festival Infantil · Old Reds · Sáb 24 Octubre</title>')
          .replace('content="Festival Infantil Old Reds — Sáb 25 Julio"',
                   'content="Festival Infantil Old Reds — Sáb 24 Octubre"'))
# Mapa: 11 canchas en 5 columnas
cabeza = cabeza.replace(
    '.lgrid{display:grid;grid-template-columns:1fr 1fr 1fr 1fr 1.4fr;',
    '.lgrid{display:grid;grid-template-columns:1fr 1fr 1fr 1fr 1.4fr;')  # no-op guard
cabeza = cabeza.replace(
    '.lgrid{display:grid;grid-template-columns:1fr 1fr 1fr 1.4fr;gap:6px;',
    '.lgrid{display:grid;grid-template-columns:repeat(5,1fr);gap:6px;')
cabeza = cabeza.replace('.lc{border-radius:6px;padding:14px 4px;color:#fff}',
                        '.lc{border-radius:6px;padding:14px 2px;color:#fff;line-height:1.25}\n'
                        '.lx{font-size:10px;font-weight:600;color:var(--dim);text-align:center;padding:2px 0;letter-spacing:.3px}')

medio = '''<div class="hero">
''' + re.search(r'<div class="hero">\n(<img [^\n]*>)', tpl).group(1) + '''
<h1>Festival Infantil</h1>
<p>SUB 10 · SUB 8 · SUB 6 — Sábado 24 de octubre · Cancha UC · Old Reds</p>
</div>

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

'''

pie = '''<footer>
<p style="margin-bottom:8px"><a href="https://oldreds.vercel.app" style="color:var(--or-red);text-decoration:underline">Ir al sitio de Old Reds</a></p>Old Reds Hockey · Festival Infantil 24/10 · Cancha UC</footer>
'''

# 4. Ajustes al script ----------------------------------------------------------
def rep(s, a, b, n=1):
    assert s.count(a) == n, (a, s.count(a))
    return s.replace(a, b)

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
# Orden alfabético en español (ÁGUILAS junto a ALUMNI, no al final)
script = rep(script, "    return Object.keys(s).sort();\n",
             "    return Object.keys(s).sort(function(a,b){return a.localeCompare(b,'es',{numeric:true});});\n", 2)
# El huevo de pascua de COGS 2 era del equipo de julio: se saca hasta confirmar
script = re.sub(r"  // Easter 2:.*?\n  \};\n\n", "", script, flags=re.S)
assert 'Juega la Lau' not in script

open(salida_path, 'w', encoding='utf-8').write(cabeza + medio + secciones_html + pie + script)

total = sum(1 for n in canchas for p in canchas[n] if p[1] != 'RIEGO')
print('canchas:', {n: sum(1 for p in canchas[n] if p[1] != 'RIEGO') for n in canchas})
print('partidos:', total)
