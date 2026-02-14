"""Template engine for doorway pages (Jinja2)."""

from jinja2 import Environment, BaseLoader, select_autoescape
from typing import Optional

from app.services.anti_detection import shuffle_block_order


# Block names for structural variation (order randomized per page)
DEFAULT_BLOCKS = ["content", "trust", "comparison", "cta"]


# Layout variants: different class prefixes / structure (anti-fingerprint)
LAYOUT_CSS_VARIANTS = [
    {"main": "dv-main", "cta": "cta", "trust": "trust-elements"},
    {"main": "content-wrap", "cta": "btn-cta", "trust": "badges"},
    {"main": "page-body", "cta": "cta", "trust": "trust-elements"},
]

DEFAULT_PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="{{ language }}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }}</title>
    <meta name="description" content="{{ meta_description }}">
    {% if canonical_url %}<link rel="canonical" href="{{ canonical_url }}">{% endif %}
    {% if faq_schema %}<script type="application/ld+json">{{ faq_schema | safe }}</script>{% endif %}
    {% if article_schema %}{{ article_schema | safe }}{% endif %}
    <style>
        body { font-family: system-ui, sans-serif; max-width: 800px; margin: 0 auto; padding: 2rem; line-height: 1.6; }
        h1 { color: #16a34a; margin-bottom: 1rem; }
        .cta, .btn-cta { display: inline-block; margin-top: 1rem; padding: 0.75rem 1.5rem; background: #22c55e; color: white; text-decoration: none; border-radius: 0.5rem; }
        .cta:hover, .btn-cta:hover { background: #16a34a; }
        .trust-elements, .badges { display: flex; gap: 1rem; margin: 1.5rem 0; flex-wrap: wrap; }
        .trust-elements span, .badges span { font-size: 0.85rem; color: #16a34a; }
        .comparison-table { margin: 1.5rem 0; overflow-x: auto; }
        .comparison-table table { width: 100%; border-collapse: collapse; }
        .comparison-table th, .comparison-table td { border: 1px solid #e5e7eb; padding: 0.5rem 0.75rem; text-align: left; }
        .exit-modal { position: fixed; inset: 0; background: rgba(0,0,0,0.5); z-index: 9999; display: flex; align-items: center; justify-content: center; }
        .exit-modal-content { background: white; padding: 2rem; border-radius: 0.5rem; max-width: 400px; position: relative; }
        .exit-close { position: absolute; top: 0.5rem; right: 0.5rem; background: none; border: none; font-size: 1.5rem; cursor: pointer; }
        .exit-cta { margin-top: 1rem; }
    </style>
</head>
<body class="{{ body_class }}">
    {{ main_content | safe }}
    {% if exit_intent_enabled and affiliate_url %}
    <div id="exit-intent-modal" class="exit-modal" style="display:none"><div class="exit-modal-content"><p>Подождите! Специальное предложение для вас</p><a href="{{ affiliate_url }}" class="cta exit-cta" rel="nofollow">Получить скидку</a><button class="exit-close">&times;</button></div></div>
    {% endif %}
</body>
</html>
"""


def _build_main_content(
    content: str,
    trust_elements: Optional[str],
    comparison_table: Optional[str],
    affiliate_url: Optional[str],
    cta_class: str,
    trust_class: str,
    block_order: list,
) -> str:
    """Assemble body blocks in given order (structural randomization)."""
    blocks: dict = {
        "content": content or "",
        "trust": f'<div class="{trust_class}">{trust_elements}</div>' if trust_elements else "",
        "comparison": f'<div class="comparison-table">{comparison_table}</div>' if comparison_table else "",
        "cta": f'<p><a href="{affiliate_url}" class="{cta_class}" rel="nofollow">Узнать подробнее</a></p>' if affiliate_url else "",
    }
    parts = []
    for name in block_order:
        if blocks.get(name):
            parts.append(blocks[name])
    return "\n    ".join(parts)


def render_doorway_page(
    title: str,
    meta_description: str,
    content: str,
    *,
    language: str = "ru",
    affiliate_url: Optional[str] = None,
    canonical_url: Optional[str] = None,
    template_html: Optional[str] = None,
    faq_schema: Optional[str] = None,
    article_schema: Optional[str] = None,
    hotjar_site_id: Optional[str] = None,
    clarity_project_id: Optional[str] = None,
    exit_intent_enabled: bool = False,
    trust_elements: Optional[str] = None,
    comparison_table: Optional[str] = None,
    structural_seed: Optional[tuple] = None,
) -> str:
    """
    Render full HTML page. structural_seed=(domain, path, doorway_id) enables
    block order and layout randomization for anti-detection.
    """
    from app.services.anti_detection import get_layout_variant, shuffle_block_order

    block_order = DEFAULT_BLOCKS.copy()
    layout_idx = 0
    css_variant = LAYOUT_CSS_VARIANTS[0]

    if structural_seed:
        domain, path, doorway_id = structural_seed
        block_order = shuffle_block_order(domain, path, doorway_id, block_order)
        layout_idx = get_layout_variant(domain, path, doorway_id, len(LAYOUT_CSS_VARIANTS))
        css_variant = LAYOUT_CSS_VARIANTS[layout_idx]

    main_content = _build_main_content(
        content=content or "",
        trust_elements=trust_elements,
        comparison_table=comparison_table,
        affiliate_url=affiliate_url,
        cta_class=css_variant["cta"],
        trust_class=css_variant["trust"],
        block_order=block_order,
    )
    body_class = css_variant["main"]

    env = Environment(
        loader=BaseLoader(),
        autoescape=select_autoescape(["html", "xml"]),
    )
    tpl = env.from_string(template_html or DEFAULT_PAGE_TEMPLATE)
    html = tpl.render(
        title=title,
        meta_description=meta_description,
        main_content=main_content,
        body_class=body_class,
        language=language,
        affiliate_url=affiliate_url,
        canonical_url=canonical_url,
        faq_schema=faq_schema or "",
        article_schema=article_schema or "",
        exit_intent_enabled=bool(exit_intent_enabled),
    )
    # Inject Hotjar/Clarity before </head> so they work with any template
    scripts = []
    if hotjar_site_id and str(hotjar_site_id).strip().isdigit():
        scripts.append(f'<script>(function(h,o,t,j,a,r){{h.hj=h.hj||function(){{(h.hj.q=h.hj.q||[]).push(arguments)}};h._hjSettings={{hjid:{hotjar_site_id},hjsv:6}};a=o.getElementsByTagName("head")[0];r=o.createElement("script");r.async=1;r.src=t+h._hjSettings.hjid+j+h._hjSettings.hjsv;a.appendChild(r);}})(window,document,"https://static.hotjar.com/c/hotjar-",".js?sv=");</script>')
    if clarity_project_id:
        cid = "".join(c for c in str(clarity_project_id).strip() if c.isalnum() or c in "-_")
        if cid:
            scripts.append(f'<script type="text/javascript">(function(c,l,a,r,i,t,y){{c[a]=c[a]||function(){{(c[a].q=c[a].q||[]).push(arguments)}};t=l.createElement(r);t.async=1;t.src="https://www.clarity.ms/tag/"+i;y=l.getElementsByTagName(r)[0];y.parentNode.insertBefore(t,y);}})(window,document,"clarity","script","{cid}");</script>')
    if exit_intent_enabled:
        scripts.append("""<script>(function(){var m=document.getElementById('exit-intent-modal');if(!m)return;var shown=false;document.addEventListener('mouseout',function(e){if(shown)return;if(e.clientY<10){m.style.display='flex';shown=true;}});m.querySelector && m.querySelector('.exit-close') && m.querySelector('.exit-close').addEventListener('click',function(){m.style.display='none';});})();</script>""")
    if scripts:
        inj = "\n".join(scripts)
        if "</head>" in html:
            html = html.replace("</head>", f"{inj}\n</head>", 1)
        else:
            html = inj + "\n" + html
    return html
