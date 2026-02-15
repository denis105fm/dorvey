"""Seed default page template

Revision ID: 004
Revises: 003
Create Date: 2025-02-15

"""
from alembic import op
from sqlalchemy import text

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None

DEFAULT_TEMPLATE = r"""<!DOCTYPE html>
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


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        text(
            "INSERT INTO templates (name, type, content, variables) "
            "SELECT 'Страница по умолчанию', 'page', :content, '[]'::jsonb "
            "WHERE NOT EXISTS (SELECT 1 FROM templates LIMIT 1)"
        ),
        {"content": DEFAULT_TEMPLATE},
    )


def downgrade() -> None:
    op.execute(text("DELETE FROM templates WHERE name = 'Страница по умолчанию'"))
