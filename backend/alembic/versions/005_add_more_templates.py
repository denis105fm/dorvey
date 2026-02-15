"""Add more seed templates: Minimal, Finance

Revision ID: 005
Revises: 004
Create Date: 2025-02-15

"""
from alembic import op
from sqlalchemy import text

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None

TEMPLATE_MINIMAL = r"""<!DOCTYPE html>
<html lang="{{ language }}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }}</title>
    <meta name="description" content="{{ meta_description }}">
    {% if canonical_url %}<link rel="canonical" href="{{ canonical_url }}">{% endif %}
    {% if faq_schema %}<script type="application/ld+json">{{ faq_schema | safe }}</script>{% endif %}
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; max-width: 720px; margin: 0 auto; padding: 1.5rem; line-height: 1.7; color: #1f2937; }
        h1 { font-size: 1.5rem; font-weight: 600; margin-bottom: 0.75rem; }
        a.cta { display: inline-block; margin-top: 1rem; padding: 0.6rem 1.2rem; background: #2563eb; color: white; text-decoration: none; border-radius: 0.375rem; font-size: 0.9rem; }
        a.cta:hover { background: #1d4ed8; }
    </style>
</head>
<body>
    {{ main_content | safe }}
</body>
</html>
"""

TEMPLATE_FINANCE = r"""<!DOCTYPE html>
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
        body { font-family: Georgia, serif; max-width: 820px; margin: 0 auto; padding: 2rem; line-height: 1.65; color: #111; }
        h1 { font-size: 1.75rem; color: #0f766e; margin-bottom: 1rem; border-bottom: 2px solid #14b8a6; padding-bottom: 0.5rem; }
        .trust-row { display: flex; gap: 1.5rem; margin: 1.25rem 0; font-size: 0.85rem; color: #0d9488; }
        .trust-row span::before { content: "✓ "; }
        .comparison-table { margin: 1.5rem 0; border: 1px solid #e2e8f0; border-radius: 0.5rem; overflow: hidden; }
        .comparison-table table { width: 100%; border-collapse: collapse; }
        .comparison-table th, .comparison-table td { padding: 0.6rem 0.9rem; text-align: left; border-bottom: 1px solid #e2e8f0; }
        .comparison-table th { background: #f8fafc; font-weight: 600; }
        .cta { display: inline-block; margin-top: 1.25rem; padding: 0.75rem 1.5rem; background: #0d9488; color: white; text-decoration: none; border-radius: 0.5rem; font-weight: 500; }
        .cta:hover { background: #0f766e; }
        .exit-modal { position: fixed; inset: 0; background: rgba(0,0,0,0.4); z-index: 9999; display: flex; align-items: center; justify-content: center; }
        .exit-modal-content { background: white; padding: 2rem; border-radius: 0.5rem; max-width: 400px; box-shadow: 0 10px 40px rgba(0,0,0,0.15); }
        .exit-close { float: right; background: none; border: none; font-size: 1.25rem; cursor: pointer; }
    </style>
</head>
<body class="{{ body_class }}">
    {{ main_content | safe }}
    {% if exit_intent_enabled and affiliate_url %}
    <div id="exit-intent-modal" class="exit-modal" style="display:none"><div class="exit-modal-content"><button class="exit-close">&times;</button><p>Выгодное предложение — ограничено по времени</p><a href="{{ affiliate_url }}" class="cta" rel="nofollow">Оформить заявку</a></div></div>
    {% endif %}
</body>
</html>
"""


def upgrade() -> None:
    conn = op.get_bind()
    for name, content in [
        ("Минималистичный", TEMPLATE_MINIMAL),
        ("Финансовый", TEMPLATE_FINANCE),
    ]:
        conn.execute(
            text(
                "INSERT INTO templates (name, type, content, variables) "
                "SELECT :name, 'page', :content, '[]'::jsonb "
                "WHERE NOT EXISTS (SELECT 1 FROM templates WHERE name = :name2)"
            ),
            {"name": name, "content": content, "name2": name},
        )


def downgrade() -> None:
    op.execute(text("DELETE FROM templates WHERE name IN ('Минималистичный', 'Финансовый')"))
