from flask import render_template, Response, request
from core import app
from datetime import datetime

# ─── robots.txt ────────────────────────────────────────────────────────────────

@app.route('/robots.txt')
def robots_txt():
    content = """User-agent: *
Allow: /
Allow: /tarifs
Allow: /blog
Allow: /demo
Allow: /register
Disallow: /superadmin
Disallow: /api/
Disallow: /static/

Sitemap: https://www.syndicpro.tn/sitemap.xml
"""
    return Response(content, mimetype='text/plain')


# ─── sitemap.xml ───────────────────────────────────────────────────────────────

@app.route('/sitemap.xml')
def sitemap_xml():
    today = datetime.utcnow().strftime('%Y-%m-%d')
    pages = [
        ('https://www.syndicpro.tn/',                                    today, 'weekly',  '1.0'),
        ('https://www.syndicpro.tn/tarifs',                              today, 'monthly', '0.9'),
        ('https://www.syndicpro.tn/demo',                                today, 'monthly', '0.8'),
        ('https://www.syndicpro.tn/register',                            today, 'monthly', '0.8'),
        ('https://www.syndicpro.tn/blog',                                today, 'weekly',  '0.8'),
        ('https://www.syndicpro.tn/blog/gerer-copropriete-tunisie',      today, 'monthly', '0.7'),
        ('https://www.syndicpro.tn/blog/obligations-syndic-tunisie',     today, 'monthly', '0.7'),
        ('https://www.syndicpro.tn/blog/logiciel-syndic-vs-excel',       today, 'monthly', '0.7'),
        ('https://www.syndicpro.tn/blog/calcul-charges-copropriete',     today, 'monthly', '0.7'),
    ]
    urls = ''
    for loc, lastmod, freq, prio in pages:
        urls += f"""  <url>
    <loc>{loc}</loc>
    <lastmod>{lastmod}</lastmod>
    <changefreq>{freq}</changefreq>
    <priority>{prio}</priority>
  </url>\n"""

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{urls}</urlset>"""
    return Response(xml, mimetype='application/xml')


# ─── Page /tarifs ──────────────────────────────────────────────────────────────

@app.route('/bienvenue')
def bienvenue():
    org_name = request.args.get('org', 'votre résidence')
    email    = request.args.get('email', '')
    return render_template('bienvenue.html', org_name=org_name, email=email)


@app.route('/tarifs')
def tarifs():
    return render_template('tarifs.html')


# ─── Blog ──────────────────────────────────────────────────────────────────────

ARTICLES = [
    {
        'slug':    'gerer-copropriete-tunisie',
        'title':   'Comment gérer une copropriété en Tunisie : le guide complet 2025',
        'excerpt': 'Obligations légales, gestion des charges, assemblée générale et communication avec les résidents — tout ce que le syndic doit savoir.',
        'date':    '2025-04-01',
        'template':'blog/gerer-copropriete-tunisie.html',
    },
    {
        'slug':    'obligations-syndic-tunisie',
        'title':   'Obligations du syndic de copropriété en Tunisie selon la loi',
        'excerpt': 'Le rôle légal du syndic, ses responsabilités financières, administratives et juridiques selon la législation tunisienne en vigueur.',
        'date':    '2025-04-05',
        'template':'blog/obligations-syndic-tunisie.html',
    },
    {
        'slug':    'logiciel-syndic-vs-excel',
        'title':   'Logiciel de syndic vs Excel : pourquoi il est temps de changer ?',
        'excerpt': "Pourquoi continuer sur Excel coûte du temps et génère des erreurs. Les avantages concrets d'un logiciel dédié à la gestion de copropriété.",
        'date':    '2025-04-10',
        'template':'blog/logiciel-syndic-vs-excel.html',
    },
    {
        'slug':    'calcul-charges-copropriete',
        'title':   'Comment calculer les charges de copropriété en Tunisie ?',
        'excerpt': 'Méthode de calcul des quotes-parts, répartition des charges communes, fonds de travaux — guide pratique pour le syndic tunisien.',
        'date':    '2025-04-15',
        'template':'blog/calcul-charges-copropriete.html',
    },
]

_SLUG_MAP = {a['slug']: a for a in ARTICLES}


@app.route('/blog')
def blog_index():
    return render_template('blog/index.html', articles=ARTICLES)


@app.route('/blog/<slug>')
def blog_article(slug):
    article = _SLUG_MAP.get(slug)
    if not article:
        from flask import abort
        abort(404)
    return render_template(article['template'], article=article, all_articles=ARTICLES)
