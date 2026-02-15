"""Add quality full-featured templates

Revision ID: 006
Revises: 005
Create Date: 2025-02-15

"""
from alembic import op
from sqlalchemy import text

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None

TEMPLATES = {
    "Здоровье / wellness": r"""<!DOCTYPE html>
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
        * { box-sizing: border-box; }
        body { font-family: "Segoe UI", system-ui, sans-serif; max-width: 780px; margin: 0 auto; padding: 2rem 1.5rem; line-height: 1.7; color: #334155; background: #f8fafc; }
        h1 { font-size: 1.6rem; color: #059669; margin: 0 0 1rem; font-weight: 600; }
        .trust-elements, .badges { display: flex; gap: 1rem; margin: 1.25rem 0; flex-wrap: wrap; font-size: 0.875rem; color: #059669; }
        .trust-elements span, .badges span { padding: 0.25rem 0; }
        .comparison-table { margin: 1.5rem 0; border-radius: 0.5rem; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
        .comparison-table table { width: 100%; border-collapse: collapse; background: #fff; }
        .comparison-table th, .comparison-table td { padding: 0.65rem 1rem; text-align: left; border-bottom: 1px solid #e2e8f0; }
        .comparison-table th { background: #ecfdf5; font-weight: 600; color: #047857; }
        .cta, .btn-cta { display: inline-block; margin-top: 1.25rem; padding: 0.75rem 1.5rem; background: #10b981; color: white; text-decoration: none; border-radius: 0.5rem; font-weight: 500; transition: background 0.2s; }
        .cta:hover, .btn-cta:hover { background: #059669; }
        .exit-modal { position: fixed; inset: 0; background: rgba(5,150,105,0.15); backdrop-filter: blur(2px); z-index: 9999; display: flex; align-items: center; justify-content: center; }
        .exit-modal-content { background: #fff; padding: 2rem; border-radius: 0.75rem; max-width: 380px; box-shadow: 0 20px 50px rgba(0,0,0,0.12); }
        .exit-close { float: right; background: none; border: none; font-size: 1.5rem; cursor: pointer; color: #64748b; }
    </style>
</head>
<body class="{{ body_class }}">
    {{ main_content | safe }}
    {% if exit_intent_enabled and affiliate_url %}
    <div id="exit-intent-modal" class="exit-modal" style="display:none"><div class="exit-modal-content"><button class="exit-close">&times;</button><p>Специальное предложение для вас</p><a href="{{ affiliate_url }}" class="cta" rel="nofollow">Подробнее</a></div></div>
    {% endif %}
</body>
</html>
""",
    "E-commerce / товары": r"""<!DOCTYPE html>
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
        * { box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; max-width: 800px; margin: 0 auto; padding: 2rem; line-height: 1.65; color: #1e293b; }
        h1 { font-size: 1.5rem; color: #ea580c; margin: 0 0 1rem; font-weight: 700; }
        .trust-elements, .badges { display: flex; gap: 1rem; margin: 1rem 0; flex-wrap: wrap; font-size: 0.8rem; color: #b45309; }
        .comparison-table { margin: 1.5rem 0; border: 1px solid #fed7aa; border-radius: 0.5rem; overflow: hidden; }
        .comparison-table table { width: 100%; border-collapse: collapse; }
        .comparison-table th, .comparison-table td { padding: 0.6rem 1rem; text-align: left; border-bottom: 1px solid #fed7aa; }
        .comparison-table th { background: #fff7ed; font-weight: 600; }
        .cta, .btn-cta { display: inline-block; margin-top: 1rem; padding: 0.8rem 1.6rem; background: #f97316; color: white; text-decoration: none; border-radius: 0.5rem; font-weight: 600; }
        .cta:hover, .btn-cta:hover { background: #ea580c; }
        .exit-modal { position: fixed; inset: 0; background: rgba(0,0,0,0.4); z-index: 9999; display: flex; align-items: center; justify-content: center; }
        .exit-modal-content { background: #fff; padding: 2rem; border-radius: 0.5rem; max-width: 400px; }
        .exit-close { position: absolute; top: 0.5rem; right: 0.5rem; background: none; border: none; font-size: 1.5rem; cursor: pointer; }
    </style>
</head>
<body class="{{ body_class }}">
    {{ main_content | safe }}
    {% if exit_intent_enabled and affiliate_url %}
    <div id="exit-intent-modal" class="exit-modal" style="display:none"><div class="exit-modal-content" style="position:relative"><button class="exit-close">&times;</button><p>Скидка при переходе по ссылке</p><a href="{{ affiliate_url }}" class="cta" rel="nofollow">Перейти</a></div></div>
    {% endif %}
</body>
</html>
""",
    "Медиа / редакционный": r"""<!DOCTYPE html>
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
        body { font-family: "Georgia", "Times New Roman", serif; max-width: 680px; margin: 0 auto; padding: 2.5rem 1.5rem; line-height: 1.8; color: #1c1917; }
        h1 { font-size: 1.75rem; font-weight: 400; margin: 0 0 1.25rem; color: #1c1917; letter-spacing: -0.02em; }
        .trust-elements, .badges { display: flex; gap: 1.5rem; margin: 1.5rem 0; font-size: 0.8rem; color: #78716c; font-family: system-ui, sans-serif; }
        .comparison-table { margin: 1.75rem 0; font-family: system-ui, sans-serif; }
        .comparison-table table { width: 100%; border-collapse: collapse; font-size: 0.95rem; }
        .comparison-table th, .comparison-table td { padding: 0.6rem 0.8rem; text-align: left; border-bottom: 1px solid #e7e5e4; }
        .comparison-table th { font-weight: 600; color: #44403c; }
        .cta, .btn-cta { display: inline-block; margin-top: 1.5rem; padding: 0.6rem 1.2rem; background: #1c1917; color: #fff; text-decoration: none; border-radius: 0.25rem; font-family: system-ui, sans-serif; font-size: 0.9rem; }
        .cta:hover, .btn-cta:hover { background: #44403c; }
        .exit-modal { position: fixed; inset: 0; background: rgba(0,0,0,0.5); z-index: 9999; display: flex; align-items: center; justify-content: center; }
        .exit-modal-content { background: #fff; padding: 2rem; border-radius: 0.25rem; max-width: 400px; }
        .exit-close { float: right; background: none; border: none; font-size: 1.25rem; cursor: pointer; }
    </style>
</head>
<body class="{{ body_class }}">
    {{ main_content | safe }}
    {% if exit_intent_enabled and affiliate_url %}
    <div id="exit-intent-modal" class="exit-modal" style="display:none"><div class="exit-modal-content"><button class="exit-close">&times;</button><p>Полезная ссылка по теме</p><a href="{{ affiliate_url }}" class="cta" rel="nofollow">Читать далее</a></div></div>
    {% endif %}
</body>
</html>
""",
    "Премиум / тёмный акцент": r"""<!DOCTYPE html>
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
        body { font-family: "Inter", -apple-system, sans-serif; max-width: 740px; margin: 0 auto; padding: 2.5rem; line-height: 1.7; color: #374151; }
        h1 { font-size: 1.6rem; color: #111827; margin: 0 0 1rem; font-weight: 600; }
        .trust-elements, .badges { display: flex; gap: 1.25rem; margin: 1.25rem 0; font-size: 0.8rem; color: #6b7280; }
        .comparison-table { margin: 1.5rem 0; border: 1px solid #e5e7eb; border-radius: 0.5rem; overflow: hidden; }
        .comparison-table table { width: 100%; border-collapse: collapse; }
        .comparison-table th, .comparison-table td { padding: 0.7rem 1rem; text-align: left; border-bottom: 1px solid #e5e7eb; }
        .comparison-table th { background: #f9fafb; font-weight: 600; color: #111827; }
        .cta, .btn-cta { display: inline-block; margin-top: 1.25rem; padding: 0.75rem 1.5rem; background: #111827; color: white; text-decoration: none; border-radius: 0.5rem; font-weight: 500; }
        .cta:hover, .btn-cta:hover { background: #374151; }
        .exit-modal { position: fixed; inset: 0; background: rgba(17,24,39,0.6); z-index: 9999; display: flex; align-items: center; justify-content: center; }
        .exit-modal-content { background: #fff; padding: 2rem; border-radius: 0.5rem; max-width: 400px; box-shadow: 0 25px 50px rgba(0,0,0,0.2); }
        .exit-close { position: absolute; top: 0.5rem; right: 0.5rem; background: none; border: none; font-size: 1.5rem; cursor: pointer; color: #6b7280; }
    </style>
</head>
<body class="{{ body_class }}">
    {{ main_content | safe }}
    {% if exit_intent_enabled and affiliate_url %}
    <div id="exit-intent-modal" class="exit-modal" style="display:none"><div class="exit-modal-content" style="position:relative"><button class="exit-close">&times;</button><p>Эксклюзивное предложение</p><a href="{{ affiliate_url }}" class="cta" rel="nofollow">Получить доступ</a></div></div>
    {% endif %}
</body>
</html>
""",
    "Полный (все блоки)": r"""<!DOCTYPE html>
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
        * { box-sizing: border-box; }
        body { font-family: system-ui, -apple-system, sans-serif; max-width: 820px; margin: 0 auto; padding: 2rem 1.5rem; line-height: 1.7; color: #1f2937; }
        h1 { font-size: 1.65rem; color: #0369a1; margin: 0 0 0.5rem; font-weight: 600; }
        h2 { font-size: 1.1rem; margin: 1.5rem 0 0.5rem; color: #0c4a6e; }
        .trust-elements, .badges { display: flex; gap: 1rem; margin: 1rem 0; flex-wrap: wrap; padding: 0.75rem 0; border-top: 1px solid #e0f2fe; border-bottom: 1px solid #e0f2fe; font-size: 0.85rem; color: #0284c7; }
        .trust-elements span, .badges span { white-space: nowrap; }
        .comparison-table { margin: 1.5rem 0; overflow-x: auto; border-radius: 0.5rem; border: 1px solid #bae6fd; }
        .comparison-table table { width: 100%; border-collapse: collapse; }
        .comparison-table th, .comparison-table td { padding: 0.65rem 1rem; text-align: left; border-bottom: 1px solid #e0f2fe; }
        .comparison-table th { background: #f0f9ff; font-weight: 600; color: #0369a1; }
        .cta, .btn-cta { display: inline-block; margin: 1rem 0; padding: 0.75rem 1.5rem; background: #0284c7; color: white; text-decoration: none; border-radius: 0.5rem; font-weight: 500; }
        .cta:hover, .btn-cta:hover { background: #0369a1; }
        .exit-modal { position: fixed; inset: 0; background: rgba(2,132,199,0.1); z-index: 9999; display: flex; align-items: center; justify-content: center; }
        .exit-modal-content { background: #fff; padding: 2rem; border-radius: 0.5rem; max-width: 400px; box-shadow: 0 10px 40px rgba(0,0,0,0.1); border: 1px solid #bae6fd; }
        .exit-close { float: right; background: none; border: none; font-size: 1.5rem; cursor: pointer; line-height: 1; }
    </style>
</head>
<body class="{{ body_class }}">
    <main>
        {{ main_content | safe }}
    </main>
    {% if exit_intent_enabled and affiliate_url %}
    <div id="exit-intent-modal" class="exit-modal" style="display:none"><div class="exit-modal-content"><button class="exit-close">&times;</button><p>Подождите! У нас есть выгодное предложение</p><a href="{{ affiliate_url }}" class="cta" rel="nofollow">Узнать подробнее</a></div></div>
    {% endif %}
</body>
</html>
""",
}


def upgrade() -> None:
    conn = op.get_bind()
    for name, content in TEMPLATES.items():
        conn.execute(
            text(
                "INSERT INTO templates (name, type, content, variables) "
                "SELECT :name, 'page', :content, '[]'::jsonb "
                "WHERE NOT EXISTS (SELECT 1 FROM templates WHERE name = :name2)"
            ),
            {"name": name, "content": content, "name2": name},
        )


def downgrade() -> None:
    op.execute(text(
        """DELETE FROM templates WHERE name IN (
            'Здоровье / wellness', 'E-commerce / товары', 'Медиа / редакционный',
            'Премиум / тёмный акцент', 'Полный (все блоки)'
        )"""
    ))
