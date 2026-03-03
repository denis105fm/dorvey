"""Template engine for doorway pages (Jinja2)."""

from jinja2 import Environment, BaseLoader, select_autoescape
from typing import Optional

from app.services.anti_detection import shuffle_block_order


# Block names for structural variation (order randomized per page)
DEFAULT_BLOCKS = ["content", "trust", "urgency", "comparison", "quiz", "social_proof", "faq", "internal_links", "cta", "cta_footer"]


# Layout variants: different class prefixes / structure (anti-fingerprint)
LAYOUT_CSS_VARIANTS = [
    {"main": "dv-main", "cta": "cta", "trust": "trust-elements"},
    {"main": "content-wrap", "cta": "btn-cta", "trust": "badges"},
    {"main": "page-body", "cta": "cta", "trust": "trust-elements"},
    {"main": "article-body", "cta": "cta cta-large", "trust": "trust-elements"},
    {"main": "main-content", "cta": "btn-cta cta-large", "trust": "badges"},
    {"main": "post-content", "cta": "action-btn", "trust": "trust-badges"},
    {"main": "entry-content", "cta": "link-cta", "trust": "guarantees"},
]

DEFAULT_PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="{{ language }}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }}</title>
    <meta name="description" content="{{ meta_description }}">
    {% if canonical_url %}<link rel="canonical" href="{{ canonical_url }}">{% endif %}
    {% if og_image_url %}<meta property="og:image" content="{{ og_image_url }}">{% endif %}
    {% if faq_schema %}<script type="application/ld+json">{{ faq_schema | safe }}</script>{% endif %}
    {% if article_schema %}{{ article_schema | safe }}{% endif %}
    <style>
        body { font-family: system-ui, sans-serif; max-width: 800px; margin: 0 auto; padding: 2rem; line-height: 1.6; }
        h1 { color: #16a34a; margin-bottom: 1rem; }
        .cta, .btn-cta, .action-btn, .link-cta { display: inline-block; margin-top: 1rem; padding: 0.75rem 1.5rem; background: #22c55e; color: white; text-decoration: none; border-radius: 0.5rem; }
        .cta:hover, .btn-cta:hover, .action-btn:hover, .link-cta:hover { background: #16a34a; }
        .cta-large, .btn-cta.cta-large { padding: 1rem 2rem; font-size: 1.1rem; }
        .trust-elements, .badges, .trust-badges, .guarantees { display: flex; gap: 1rem; margin: 1.5rem 0; flex-wrap: wrap; }
        .trust-elements span, .badges span, .trust-badges span, .guarantees span { font-size: 0.85rem; color: #16a34a; }
        .comparison-table { margin: 1.5rem 0; overflow-x: auto; }
        .comparison-table table { width: 100%; border-collapse: collapse; }
        .comparison-table th, .comparison-table td { border: 1px solid #e5e7eb; padding: 0.5rem 0.75rem; text-align: left; }
        .exit-modal { position: fixed; inset: 0; background: rgba(0,0,0,0.5); z-index: 9999; display: flex; align-items: center; justify-content: center; }
        .exit-modal-content { background: white; padding: 2rem; border-radius: 0.5rem; max-width: 400px; position: relative; }
        .exit-close { position: absolute; top: 0.5rem; right: 0.5rem; background: none; border: none; font-size: 1.5rem; cursor: pointer; }
        .exit-cta { margin-top: 1rem; }
        .device-desktop .cta-mobile { display: none !important; }
        .device-mobile .cta-desktop { display: none !important; }
        .urgency-block { margin: 1rem 0; padding: 0.75rem 1rem; background: #fef3c7; border-radius: 0.5rem; font-size: 0.9rem; color: #92400e; }
        .social-proof { margin: 1rem 0; font-size: 0.9rem; color: #059669; }
        .social-proof-stats { font-weight: 600; margin-bottom: 0.25rem; }
        .social-proof-review { margin: 0.25rem 0; font-style: italic; }
        .cta-footer-wrap { margin-top: 2rem; padding-top: 1.5rem; border-top: 1px solid #e5e7eb; }
        .device-mobile .cta-footer-sticky { position: fixed; bottom: 0; left: 0; right: 0; z-index: 100; margin: 0; padding: 1rem; background: rgba(255,255,255,0.97); box-shadow: 0 -2px 12px rgba(0,0,0,0.1); border-top: 1px solid #e5e7eb; }
        .faq-block { margin: 1.5rem 0; }
        .faq-block h2 { font-size: 1.25rem; margin-bottom: 0.75rem; color: #111; }
        .faq-item { margin: 0.75rem 0; padding-bottom: 0.75rem; border-bottom: 1px solid #e5e7eb; }
        .faq-item h3 { font-size: 1rem; font-weight: 600; margin: 0 0 0.25rem 0; color: #16a34a; }
        .faq-item p { margin: 0; font-size: 0.95rem; }
        .internal-links-wrap { margin: 1.5rem 0; }
        .internal-links-wrap h2 { font-size: 1.25rem; margin-bottom: 0.75rem; color: #111; }
        .internal-links-list { list-style: none; padding: 0; margin: 0; }
        .internal-links-list li { margin: 0.5rem 0; }
        .internal-links-list a { color: #16a34a; text-decoration: none; }
        .internal-links-list a:hover { text-decoration: underline; }
        .dv-quiz { margin: 1.5rem 0; padding: 1.25rem; background: #f0fdf4; border-radius: 0.5rem; border: 1px solid #bbf7d0; }
        .dv-quiz h2 { font-size: 1.2rem; margin-bottom: 1rem; color: #166534; }
        .dv-quiz-question { margin-bottom: 1rem; }
        .dv-quiz-options { display: flex; flex-direction: column; gap: 0.5rem; }
        .dv-quiz-options button { padding: 0.65rem 1rem; text-align: left; background: #fff; border: 1px solid #86efac; border-radius: 0.375rem; cursor: pointer; font-size: 0.95rem; }
        .dv-quiz-options button:hover { background: #dcfce7; }
        .dv-quiz-nav { margin-top: 1rem; }
    </style>
</head>
<body class="{{ body_class }}"{% if data_offers %} data-offers="{{ data_offers | e }}" data-doorway-id="{{ doorway_id | default('') }}"{% endif %}>
    {{ main_content | safe }}
    {% if push_block %}{{ push_block | safe }}{% endif %}
    {% if email_capture_block %}{{ email_capture_block | safe }}{% endif %}
    {% if exit_intent_enabled and affiliate_url %}
    <div id="exit-intent-modal" class="exit-modal" style="display:none"><div class="exit-modal-content"><p>{{ exit_intent_title | default('Подождите! Специальное предложение для вас') }}</p><a href="{{ affiliate_url }}" class="cta exit-cta" rel="nofollow">{{ exit_intent_cta | default('Получить скидку') }}</a><button class="exit-close">&times;</button></div></div>
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
    cta_desktop: Optional[str] = None,
    cta_mobile: Optional[str] = None,
    urgency_block: Optional[str] = None,
    social_proof_block: Optional[str] = None,
    cta_footer: bool = True,
    faq_block: Optional[str] = None,
    internal_links_block: Optional[str] = None,
    quiz_block: Optional[str] = None,
    default_cta: str = "Learn more",
) -> str:
    """Assemble body blocks in given order (structural randomization)."""
    cta_html = ""
    if affiliate_url:
        if cta_desktop and cta_mobile:
            cta_html = (
                f'<p><span class="cta-desktop"><a href="{affiliate_url}" class="{cta_class}" rel="nofollow">'
                f"{cta_desktop}</a></span>"
                f'<span class="cta-mobile"><a href="{affiliate_url}" class="{cta_class}" rel="nofollow">'
                f"{cta_mobile}</a></span></p>"
            )
        else:
            cta_html = (
                f'<p><a href="{affiliate_url}" class="{cta_class}" rel="nofollow">'
                f"{cta_desktop or cta_mobile or default_cta}</a></p>"
            )
    cta_footer_html = ""
    if affiliate_url and cta_footer:
        cta_footer_html = (
            f'<div class="cta-footer-wrap cta-footer-sticky">'
            f'<p><a href="{affiliate_url}" class="{cta_class} cta-footer-btn" rel="nofollow">'
            f"{cta_desktop or cta_mobile or default_cta}</a></p></div>"
        )
    blocks: dict = {
        "content": content or "",
        "trust": f'<div class="{trust_class}">{trust_elements}</div>' if trust_elements else "",
        "urgency": f'<div class="urgency-block">{urgency_block}</div>' if urgency_block else "",
        "comparison": f'<div class="comparison-table">{comparison_table}</div>' if comparison_table else "",
        "social_proof": f'<div class="social-proof">{social_proof_block}</div>' if social_proof_block else "",
        "faq": f'<div class="faq-block">{faq_block}</div>' if faq_block else "",
        "internal_links": f'<div class="internal-links-wrap">{internal_links_block}</div>' if internal_links_block else "",
        "quiz": quiz_block or "",
        "cta": cta_html,
        "cta_footer": cta_footer_html,
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
    layout_index_override: Optional[int] = None,
    cta_desktop: Optional[str] = None,
    cta_mobile: Optional[str] = None,
    urgency_block: Optional[str] = None,
    social_proof_block: Optional[str] = None,
    exit_intent_title: Optional[str] = None,
    exit_intent_cta: Optional[str] = None,
    data_offers: Optional[str] = None,
    doorway_id: Optional[int] = None,
    cta_footer: bool = True,
    faq_block: Optional[str] = None,
    internal_links_block: Optional[str] = None,
    quiz_block: Optional[str] = None,
    visitor_capture: bool = False,
    analytics_base: Optional[str] = None,
    push_subscribe_enabled: bool = False,
    vapid_public_key: Optional[str] = None,
    email_capture_enabled: bool = False,
    facebook_pixel_id: Optional[str] = None,
    google_ads_id: Optional[str] = None,
    og_image_url: Optional[str] = None,
) -> str:
    """
    Render full HTML page. structural_seed=(domain, path, doorway_id) enables
    block order and layout randomization for anti-detection.
    """
    from app.services.anti_detection import get_layout_variant, shuffle_block_order
    from app.services.schema_helper import get_doorway_ui_strings

    lang = (language or "en").lower()[:2]
    ui = get_doorway_ui_strings(lang)
    def _js(s: str) -> str:
        return (s or "").replace("\\", "\\\\").replace("'", "\\'").replace("\r", "").replace("\n", " ")

    block_order = DEFAULT_BLOCKS.copy()
    layout_idx = 0
    css_variant = LAYOUT_CSS_VARIANTS[0]

    _dw_id = None
    if structural_seed:
        domain, path, _dw_id = structural_seed
        block_order = shuffle_block_order(domain, path, _dw_id, block_order)
        if layout_index_override is not None and 0 <= layout_index_override < len(LAYOUT_CSS_VARIANTS):
            layout_idx = layout_index_override
        else:
            layout_idx = get_layout_variant(domain, path, _dw_id, len(LAYOUT_CSS_VARIANTS))
        css_variant = LAYOUT_CSS_VARIANTS[layout_idx]

    main_content = _build_main_content(
        content=content or "",
        trust_elements=trust_elements,
        comparison_table=comparison_table,
        affiliate_url=affiliate_url,
        cta_class=css_variant["cta"],
        trust_class=css_variant["trust"],
        block_order=block_order,
        cta_desktop=cta_desktop,
        cta_mobile=cta_mobile,
        urgency_block=urgency_block,
        social_proof_block=social_proof_block,
        cta_footer=cta_footer,
        faq_block=faq_block,
        internal_links_block=internal_links_block,
        quiz_block=quiz_block,
        default_cta=ui.get("default_cta", "Learn more"),
    )
    body_class = css_variant["main"]

    # Build push subscribe block before render
    push_block = ""
    if push_subscribe_enabled and vapid_public_key and analytics_base and (doorway_id is not None or _dw_id is not None):
        dw_id = doorway_id if doorway_id is not None else _dw_id
        base_esc = analytics_base.replace("\\", "\\\\").replace("'", "\\'")
        vapid_esc = (vapid_public_key or "").replace("\\", "\\\\").replace("'", "\\'")
        push_block = f'''<div id="dv-push-modal" class="dv-push-modal" style="display:none;position:fixed;inset:0;z-index:99999;background:rgba(0,0,0,0.6);align-items:center;justify-content:center;">
<div class="dv-push-box" style="background:#fff;border-radius:12px;padding:1.75rem;max-width:360px;box-shadow:0 25px 50px -12px rgba(0,0,0,0.25);text-align:center;margin:1rem;">
<p style="margin:0 0 0.5rem;font-size:1.25rem;font-weight:600;color:#111;">{ui.get("push_title", "Don't miss out!")}</p>
<p style="margin:0 0 1.25rem;font-size:0.95rem;color:#555;line-height:1.5;">{ui.get("push_desc", "Allow notifications for deals.")}</p>
<button type="button" id="dv-push-btn" class="cta" style="width:100%;padding:0.9rem 1.5rem;font-size:1rem;font-weight:600;margin:0 0 0.5rem;">{ui.get("push_btn", "Allow notifications")}</button>
<p id="dv-push-status" style="margin:0 0 0.5rem;font-size:0.85rem;color:#15803d"></p>
<a href="#" id="dv-push-later" style="font-size:0.8rem;color:#888;text-decoration:none;">{ui.get("push_later", "Later")}</a>
</div>
</div>
<div class="push-subscribe-inline" style="margin:1.5rem 0;padding:0.75rem;background:#f0fdf4;border-radius:0.5rem;text-align:center;">
<button type="button" id="dv-push-btn-inline" class="cta" style="margin:0">{ui.get("push_subscribe_btn", "Subscribe to notifications")}</button>
<p id="dv-push-status-inline" style="margin:0.5rem 0 0;font-size:0.85rem;color:#15803d"></p>
</div>
<script>(function(){{
var base='{base_esc}';
var vapidB64='{vapid_esc}';
var dw={dw_id};
var modal=document.getElementById('dv-push-modal');
var btnModal=document.getElementById('dv-push-btn');
var btnInline=document.getElementById('dv-push-btn-inline');
var statusEl=document.getElementById('dv-push-status');
var statusInline=document.getElementById('dv-push-status-inline');
var txtLoad='{_js(ui.get("push_loading", "Loading..."))}';
var txtDone='{_js(ui.get("push_done", "Done!"))}';
var txtDenied='{_js(ui.get("push_denied", "Permission denied"))}';
var txtSubscribed='{_js(ui.get("push_subscribed", "You\'re subscribed"))}';
function urlB64ToUint8Array(b64){{
  var padding='='.repeat((4-b64.length%4)%4);
  b64=(b64+padding).replace(/-/g,'+').replace(/_/g,'/');
  var raw=atob(b64); var out=new Uint8Array(raw.length);
  for(var i=0;i<raw.length;i++)out[i]=raw.charCodeAt(i);
  return out;
}}
async function doSubscribe(btn,status){{
  try{{
    if(btn)btn.disabled=true;
    if(status)status.textContent=txtLoad;
    var reg=await navigator.serviceWorker.register('/sw_push.js',{{scope:'/'}});
    var perm=await Notification.requestPermission();
    if(perm!=='granted'){{if(status)status.textContent=txtDenied;if(btn)btn.disabled=false;return;}}
    var sub=await reg.pushManager.subscribe({{userVisibleOnly:true,applicationServerKey:urlB64ToUint8Array(vapidB64)}});
    var vid=localStorage.getItem('dv_vid')||'v_'+Math.random().toString(36).slice(2)+Date.now();
    localStorage.setItem('dv_vid',vid);
    await fetch(base+'/api/analytics/push-subscribe',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{visitor_id:vid,doorway_id:dw,subscription:sub.toJSON()}})}});
    if(status)status.textContent=txtDone;
    if(btn){{btn.textContent=txtSubscribed;btn.disabled=true;}}
    if(modal){{modal.style.display='none';}}
    sessionStorage.setItem('dv_push_ok','1');
  }}catch(e){{if(status)status.textContent='Error: '+e.message;if(btn)btn.disabled=false;}}
}}
function tryShowModal(){{
  if(!('serviceWorker' in navigator)||!('PushManager' in window))return;
  if(sessionStorage.getItem('dv_push_shown')||sessionStorage.getItem('dv_push_ok'))return;
  if(Notification.permission==='granted')return;
  sessionStorage.setItem('dv_push_shown','1');
  modal.style.display='flex';
}}
if(btnModal)btnModal.onclick=function(){{doSubscribe(btnModal,statusEl);}};
if(btnInline)btnInline.onclick=function(){{doSubscribe(btnInline,statusInline);}};
document.getElementById('dv-push-later')&&document.getElementById('dv-push-later').addEventListener('click',function(e){{e.preventDefault();if(modal)modal.style.display='none';}});
if(!('serviceWorker' in navigator)||!('PushManager' in window)){{if(modal)modal.style.display='none';if(document.querySelector('.push-subscribe-inline'))document.querySelector('.push-subscribe-inline').style.display='none';return;}}
if('serviceWorker' in navigator)navigator.serviceWorker.register('/sw_push.js',{{scope:'/'}}).catch(function(){{}});
setTimeout(tryShowModal,6000);
var scrollShown=false;
window.addEventListener('scroll',function(){{
  if(scrollShown)return;
  var h=document.documentElement.scrollHeight-document.documentElement.clientHeight;
  if(h>100&&window.scrollY>h*0.35){{scrollShown=true;tryShowModal();}}
}},{{passive:true}});
document.addEventListener('mouseout',function(e){{
  if(e.clientY<5&&!scrollShown){{scrollShown=true;tryShowModal();}}
}},{{passive:true}});
}})();</script>'''

    # Email capture block (modal + inline form)
    email_capture_block = ""
    if email_capture_enabled and analytics_base and (doorway_id is not None or _dw_id is not None):
        dw_id_email = doorway_id if doorway_id is not None else _dw_id
        base_esc_email = analytics_base.replace("\\", "\\\\").replace("'", "\\'")
        _email_title = ui.get("email_title", "Get a personal offer")
        _email_desc = ui.get("email_desc", "Leave your email for best deals.")
        _email_ph = ui.get("email_placeholder", "your@email.com")
        _email_btn = ui.get("email_btn", "Send")
        _email_btn_short = ui.get("email_btn_short", "Get offer")
        _email_later = ui.get("email_later", "Later")
        _email_required = _js(ui.get("email_required", "Enter email"))
        _email_sending = _js(ui.get("email_sending", "Sending..."))
        _email_done = _js(ui.get("email_done", "Done! Thanks."))
        _email_error = _js(ui.get("email_error", "Error"))
        email_capture_block = f'''<div id="dv-email-modal" style="display:none;position:fixed;inset:0;z-index:99998;background:rgba(0,0,0,0.6);align-items:center;justify-content:center;">
<div style="background:#fff;border-radius:12px;padding:1.75rem;max-width:360px;box-shadow:0 25px 50px -12px rgba(0,0,0,0.25);margin:1rem;">
<p style="margin:0 0 0.5rem;font-size:1.25rem;font-weight:600;color:#111;">{_email_title}</p>
<p style="margin:0 0 1rem;font-size:0.95rem;color:#555;">{_email_desc}</p>
<input type="email" id="dv-email-input" placeholder="{_email_ph}" style="width:100%;padding:0.75rem;border:1px solid #e5e7eb;border-radius:0.5rem;margin-bottom:0.5rem;box-sizing:border-box;">
<p id="dv-email-status" style="margin:0 0 0.5rem;font-size:0.85rem;color:#15803d"></p>
<button type="button" id="dv-email-btn" class="cta" style="width:100%;padding:0.75rem;">{_email_btn}</button>
<a href="#" id="dv-email-later" style="display:block;text-align:center;margin-top:0.5rem;font-size:0.8rem;color:#888;text-decoration:none;">{_email_later}</a>
</div>
</div>
<div class="email-capture-inline" style="margin:1.5rem 0;padding:0.75rem;background:#fefce8;border-radius:0.5rem;text-align:center;">
<input type="email" id="dv-email-inline" placeholder="{_email_ph}" style="max-width:280px;padding:0.5rem 0.75rem;margin-right:0.5rem;border:1px solid #e5e7eb;border-radius:0.5rem;">
<button type="button" id="dv-email-btn-inline" class="cta" style="padding:0.5rem 1rem;">{_email_btn_short}</button>
<p id="dv-email-status-inline" style="margin:0.5rem 0 0;font-size:0.85rem;color:#15803d"></p>
</div>
<script>(function(){{
var base='{base_esc_email}'; var dw={dw_id_email};
var txtRequired='{_email_required}'; var txtSending='{_email_sending}'; var txtDone='{_email_done}'; var txtError='{_email_error}';
function getVid(){{return localStorage.getItem('dv_vid')||'';}}
function doEmailSubmit(input,btn,status){{
  var email=(input.value||'').trim().toLowerCase();
  if(!email){{if(status)status.textContent=txtRequired;return;}}
  if(btn)btn.disabled=true; if(status)status.textContent=txtSending;
  fetch(base+'/api/analytics/email-capture',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{email:email,visitor_id:getVid()||null,doorway_id:dw}})}}).then(function(r){{return r.json();}}).then(function(j){{
    if(j.detail){{if(status)status.textContent=j.detail;if(btn)btn.disabled=false;return;}}
    if(status)status.textContent=txtDone;if(btn)btn.disabled=true;input.value='';
    var m=document.getElementById('dv-email-modal');if(m)m.style.display='none';sessionStorage.setItem('dv_email_ok','1');
  }}).catch(function(){{if(status)status.textContent=txtError;if(btn)btn.disabled=false;}});
}}
function tryShowEmailModal(){{
  if(sessionStorage.getItem('dv_email_shown')||sessionStorage.getItem('dv_email_ok'))return;
  sessionStorage.setItem('dv_email_shown','1');
  var m=document.getElementById('dv-email-modal');if(m){{m.style.display='flex';}}
}}
var ei=document.getElementById('dv-email-input');var eib=document.getElementById('dv-email-btn');
var eii=document.getElementById('dv-email-inline');var eibi=document.getElementById('dv-email-btn-inline');
var es=document.getElementById('dv-email-status');var esi=document.getElementById('dv-email-status-inline');
if(eib)eib.onclick=function(){{doEmailSubmit(ei,eib,es);}};
if(eibi)eibi.onclick=function(){{doEmailSubmit(eii,eibi,esi);}};
if(ei)ei.addEventListener('keypress',function(e){{if(e.key==='Enter')doEmailSubmit(ei,eib,es);}});
if(eii)eii.addEventListener('keypress',function(e){{if(e.key==='Enter')doEmailSubmit(eii,eibi,esi);}});
document.getElementById('dv-email-later')&&document.getElementById('dv-email-later').addEventListener('click',function(e){{e.preventDefault();var m=document.getElementById('dv-email-modal');if(m)m.style.display='none';}});
setTimeout(tryShowEmailModal,8000);
var esc2=false;window.addEventListener('scroll',function(){{if(esc2)return;var h=document.documentElement.scrollHeight-document.documentElement.clientHeight;if(h>150&&window.scrollY>h*0.5){{esc2=true;tryShowEmailModal();}}}},{{passive:true}});
}})();</script>'''

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
        exit_intent_title=exit_intent_title or ui.get("exit_default_title", ""),
        exit_intent_cta=exit_intent_cta or ui.get("exit_default_cta", ""),
        data_offers=data_offers or "",
        doorway_id=doorway_id if doorway_id is not None else (_dw_id or ""),
        push_block=push_block,
        email_capture_block=email_capture_block,
        og_image_url=og_image_url or "",
    )
    # Inject Hotjar/Clarity before </head> so they work with any template
    scripts = []
    if hotjar_site_id:
        hid = str(hotjar_site_id).strip()
        if hid.isdigit():
            scripts.append(f'<script>(function(h,o,t,j,a,r){{h.hj=h.hj||function(){{(h.hj.q=h.hj.q||[]).push(arguments)}};h._hjSettings={{hjid:{hid},hjsv:6}};a=o.getElementsByTagName("head")[0];r=o.createElement("script");r.async=1;r.src=t+h._hjSettings.hjid+j+h._hjSettings.hjsv;a.appendChild(r);}})(window,document,"https://static.hotjar.com/c/hotjar-",".js?sv=");</script>')
        else:
            # Contentsquare (Hotjar evolved) — ID вида 785bcc77e264f
            cq_id = "".join(c for c in hid if c.isalnum() or c in "-_")
            if cq_id:
                scripts.append(f'<script src="https://t.contentsquare.net/uxa/{cq_id}.js"></script>')
    if clarity_project_id:
        cid = "".join(c for c in str(clarity_project_id).strip() if c.isalnum() or c in "-_@")
        if cid:
            scripts.append(f'<script type="text/javascript">(function(c,l,a,r,i,t,y){{c[a]=c[a]||function(){{(c[a].q=c[a].q||[]).push(arguments)}};t=l.createElement(r);t.async=1;t.src="https://www.clarity.ms/tag/"+i;y=l.getElementsByTagName(r)[0];y.parentNode.insertBefore(t,y);}})(window,document,"clarity","script","{cid}");</script>')
    if exit_intent_enabled:
        scripts.append("""<script>(function(){var m=document.getElementById('exit-intent-modal');if(!m)return;var shown=false;document.addEventListener('mouseout',function(e){if(shown)return;if(e.clientY<10){m.style.display='flex';shown=true;}});m.querySelector && m.querySelector('.exit-close') && m.querySelector('.exit-close').addEventListener('click',function(){m.style.display='none';});})();</script>""")
    if facebook_pixel_id and str(facebook_pixel_id).strip().isdigit():
        fid = "".join(c for c in str(facebook_pixel_id) if c.isdigit())
        scripts.append(f'''<script>!function(f,b,e,v,n,t,s){{if(f.fbq)return;n=f.fbq=function(){{n.callMethod?n.callMethod.apply(n,arguments):n.queue.push(arguments)}};if(!f._fbq)f._fbq=n;n.push=n;n.loaded=!0;n.version="2.0";n.queue=[];t=b.createElement(e);t.async=!0;t.src=v;s=b.getElementsByTagName(e)[0];s.parentNode.insertBefore(t,s)}}(window,document,"script","https://connect.facebook.net/en_US/fbevents.js");fbq("init","{fid}");fbq("track","PageView");</script>''')
    if google_ads_id and len(str(google_ads_id).strip()) >= 5:
        gid = str(google_ads_id).strip()
        scripts.append(f'''<script async src="https://www.googletagmanager.com/gtag/js?id={gid}"></script><script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}gtag("js",new Date());gtag("config","{gid}");</script>''')
    if scripts:
        inj = "\n".join(scripts)
        if "</head>" in html:
            html = html.replace("</head>", f"{inj}\n</head>", 1)
        else:
            html = inj + "\n" + html

    # Visitor capture: vid in localStorage, visit pixel, append vid to click URLs
    visitor_script = ""
    dw_id_visitor = doorway_id if doorway_id is not None else _dw_id
    if visitor_capture and analytics_base and dw_id_visitor is not None:
        base_esc = analytics_base.replace("\\", "\\\\").replace("'", "\\'")
        visitor_script = f"""<script>(function(){{var vid=localStorage.getItem('dv_vid');if(!vid){{vid='v_'+Math.random().toString(36).slice(2)+Date.now();localStorage.setItem('dv_vid',vid)}}var dw='{dw_id_visitor}';var base='{base_esc}';var i=new Image();i.src=base+'/api/analytics/visit?dw='+dw+'&vid='+encodeURIComponent(vid);function addVidToLinks(){{var links=document.querySelectorAll('a.cta,a.btn-cta,a.action-btn,a.link-cta,a.exit-cta,.cta-footer-btn');links.forEach(function(a){{if(a.href.indexOf('analytics/click')>=0){{try{{var u=new URL(a.href);if(!u.searchParams.get('vid'))u.searchParams.set('vid',vid);a.href=u.toString()}}catch(e){{}}}}}})}}addVidToLinks();document.addEventListener('DOMContentLoaded',addVidToLinks);setTimeout(addVidToLinks,500)}})();</script>"""
    # Device + geo detection + GEO/device offer selection
    device_script = """<script>(function(){var m=/iPhone|iPad|iPod|Android|webOS|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent)||(window.innerWidth<768);document.body.classList.add(m?'device-mobile':'device-desktop');var d=m?'mobile':'desktop';function pickOffer(geo){var ob=document.body.getAttribute('data-offers');var dw=document.body.getAttribute('data-doorway-id');if(!ob||!dw)return;try{var offers=JSON.parse(ob);var best=null;var bestId=null;for(var i=0;i<offers.length;i++){var o=offers[i];if(o.geo&&geo&&o.geo.toUpperCase()!==geo)continue;if(o.device&&o.device.toLowerCase()!==d)continue;best=o.url;bestId=o.id!=null?o.id:null;break}if(!best&&offers.length){best=offers[0].url;bestId=offers[0].id!=null?offers[0].id:null}var links=document.querySelectorAll('a.cta,a.btn-cta,a.action-btn,a.link-cta,a.exit-cta,.cta-footer-btn');if(links.length&&links[0].href.indexOf('analytics/click')>=0){try{var u=new URL(links[0].href);u.searchParams.set('geo',geo||'');u.searchParams.set('device',d);if(bestId!=null)u.searchParams.set('oid',String(bestId));try{var pu=new URL(window.location.href);var utm=pu.searchParams.get('utm_source')||pu.searchParams.get('src');if(utm)u.searchParams.set('utm_source',utm)}catch(e){}links.forEach(function(a){a.href=u.toString()})}catch(e){}}else if(best){var sep=best.indexOf('?')>=0?'&':'?';var sid=bestId!=null?dw+'_'+bestId:dw;var u=best+sep+'sub_id='+sid;links.forEach(function(a){a.href=u})}}catch(e){}}fetch('https://ipapi.co/json/').then(function(r){return r.json();}).then(function(j){if(j&&j.country_code){document.body.classList.add('geo-'+j.country_code.toUpperCase());pickOffer(j.country_code.toUpperCase())}else pickOffer()}).catch(function(){pickOffer()})})();</script>"""
    if "</body>" in html:
        to_inject = visitor_script + "\n" + device_script if visitor_script else device_script
        html = html.replace("</body>", f"{to_inject}\n</body>", 1)
    return html
