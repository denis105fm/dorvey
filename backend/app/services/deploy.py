"""Deploy doorway to server via SSH."""

import html
import io
import os
from typing import Optional

# Path to service worker for push (relative to this file)
_SW_PATH = os.path.join(os.path.dirname(__file__), "..", "static", "sw_push.js")
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode

import paramiko
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.doorway import Doorway
from app.models.domain import Domain
from app.models.server import Server
from app.models.setting import Setting
from app.services.template_engine import render_doorway_page


def _get_ssh_client(server: Server) -> paramiko.SSHClient:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    connect_kw = {
        "hostname": server.host,
        "port": server.port or 22,
        "username": server.user,
    }
    if server.auth_type == "password" and server.auth_data:
        connect_kw["password"] = server.auth_data
    else:
        # SSH key: auth_data can be key content or path
        key = server.auth_data
        if key and "\n" in key:
            pkey = paramiko.RSAKey.from_private_key(io.StringIO(key))
        elif key:
            pkey = paramiko.RSAKey.from_private_key_file(key)
        else:
            pkey = None
        if pkey:
            connect_kw["pkey"] = pkey
        elif server.auth_type == "password":
            connect_kw["password"] = ""
    client.connect(**connect_kw)
    return client


def deploy_doorway_ftp(
    host: str,
    user: str,
    password: str,
    path: str,
    html_content: str,
    remote_path: str = "/",
    port: int = 21,
) -> tuple[bool, str]:
    """Deploy via FTP. Returns (success, message)."""
    try:
        from ftplib import FTP
        ftp = FTP()
        ftp.connect(host, port)
        ftp.login(user, password)
        root = remote_path.rstrip("/")
        if path in ("", "/"):
            remote = f"{root}/index.html"
        else:
            clean = path.strip("/")
            remote = f"{root}/{clean}/index.html"
        parts = remote.split("/")[:-1]
        for i in range(1, len(parts) + 1):
            d = "/".join(parts[:i])
            try:
                ftp.mkd(d)
            except Exception:
                pass
        from io import BytesIO
        buf = BytesIO(html_content.encode("utf-8"))
        dir_path = "/".join(remote.split("/")[:-1])
        if dir_path:
            try:
                ftp.cwd(dir_path)
            except Exception:
                pass
        ftp.storbinary(f"STOR {remote.split('/')[-1]}", buf)
        ftp.quit()
        return True, f"FTP deployed to {remote}"
    except Exception as e:
        return False, str(e)


def deploy_doorway_sync(
    server: Server,
    domain: str,
    path: str,
    html_content: str,
    base_path: str = "/var/www/html",
) -> tuple[bool, str]:
    """
    Upload HTML to server. Returns (success, message).
    Path like / or /page1 - becomes index.html or page1/index.html
    """
    try:
        client = _get_ssh_client(server)
        sftp = client.open_sftp()
        root = (base_path or server.path or "/var/www/html").rstrip("/")
        if path in ("", "/"):
            remote = f"{root}/index.html"
        else:
            clean = path.strip("/")
            remote = f"{root}/{clean}/index.html"
        buf = io.BytesIO(html_content.encode("utf-8"))
        try:
            # Ensure parent dir exists
            parent = "/".join(remote.split("/")[:-1])
            try:
                sftp.stat(parent)
            except FileNotFoundError:
                parts = parent.split("/")
                for i in range(2, len(parts) + 1):
                    d = "/".join(parts[:i])
                    try:
                        sftp.mkdir(d)
                    except OSError:
                        pass
            sftp.putfo(buf, remote)
        finally:
            sftp.close()
            client.close()
        return True, f"Deployed to {remote}"
    except Exception as e:
        return False, str(e)


def deploy_sw_push(server: Server, base_path: str = "/var/www/html") -> tuple[bool, str]:
    """Deploy service worker for push to web root. Returns (success, message)."""
    try:
        sw_path = os.path.normpath(_SW_PATH)
        if not os.path.isfile(sw_path):
            return False, "sw_push.js not found"
        with open(sw_path, "rb") as f:
            sw_content = f.read()
        client = _get_ssh_client(server)
        sftp = client.open_sftp()
        root = (base_path or getattr(server, "path", None) or "/var/www/html").rstrip("/")
        remote = f"{root}/sw_push.js"
        buf = io.BytesIO(sw_content)
        sftp.putfo(buf, remote)
        sftp.close()
        client.close()
        return True, f"SW deployed to {remote}"
    except Exception as e:
        return False, str(e)


def run_certbot_ssl(server: Server, domain: str, webroot: str = "/var/www/html") -> tuple[bool, str]:
    """Run certbot for domain via SSH. Returns (success, message)."""
    try:
        client = _get_ssh_client(server)
        cmd = (
            f"certbot certonly --webroot -w {webroot} -d {domain} "
            "--non-interactive --agree-tos --register-unsafely-without-email "
            "2>&1 || true"
        )
        stdin, stdout, stderr = client.exec_command(cmd, timeout=120)
        out = (stdout.read().decode() or "") + (stderr.read().decode() or "")
        client.close()
        return "Successfully received certificate" in out or "Certificate not yet due for renewal" in out, out or "OK"
    except Exception as e:
        return False, str(e)


def _append_sub_id(url: str, doorway_id: int) -> str:
    """Add sub_id=doorway_id to affiliate URL for postback attribution.
    Supports placeholders {sub_id}, {doorway_id}. Otherwise appends query param.
    """
    if not url or doorway_id <= 0:
        return url
    sid = str(doorway_id)
    if "{sub_id}" in url:
        return url.replace("{sub_id}", sid)
    if "{doorway_id}" in url:
        return url.replace("{doorway_id}", sid)
    parsed = urlparse(url)
    qs = parse_qs(parsed.query, keep_blank_values=True)
    qs["sub_id"] = [sid]
    new_query = urlencode(qs, doseq=True)
    return urlunparse(parsed._replace(query=new_query))


def _get_best_offer_url(offers: list, geo: Optional[str] = None, device: Optional[str] = None):
    """Pick best offer by geo/device. Returns URL or None."""
    if not offers:
        return None
    for o in sorted(offers, key=lambda x: -(x.priority or 0)):
        if not o.get("is_active", True):
            continue
        og, od = o.get("geo"), o.get("device")
        if geo and og and geo.upper() != og.upper():
            continue
        if device and od and device.lower() != od.lower():
            continue
        return o.get("url")
    return offers[0].get("url") if offers else None


async def prepare_doorway_html(db: AsyncSession, doorway_id: int) -> Optional[str]:
    """Load doorway and campaign/domain, return full HTML."""
    r = await db.execute(
        select(Doorway, Domain, Server)
        .join(Domain, Doorway.domain_id == Domain.id)
        .join(Server, Domain.server_id == Server.id)
        .where(Doorway.id == doorway_id)
    )
    row = r.first()
    if not row:
        return None
    dw, dom, srv = row
    from app.models.campaign import Campaign
    from app.models.offer import Offer
    camp_r = await db.execute(select(Campaign).where(Campaign.id == dw.campaign_id))
    camp = camp_r.scalar_one_or_none()
    if not camp:
        return None
    off_r = await db.execute(
        select(Offer).where(Offer.campaign_id == camp.id, Offer.is_active == True).order_by(Offer.priority.desc())
    )
    offers_raw = off_r.scalars().all()
    offers = [{"url": o.url, "name": o.name, "rate": o.rate, "amount": o.amount, "term": o.term, "geo": o.geo, "device": o.device, "priority": o.priority, "is_active": o.is_active} for o in offers_raw]
    aff_url = camp.affiliate_url
    if offers:
        aff_url = _get_best_offer_url(offers) or aff_url
    aff_url_with_sub = _append_sub_id(aff_url, dw.id) if aff_url else None

    click_base = None
    click_enabled = False
    visitor_capture = False
    vapid_public = None
    email_capture = False
    fb_pixel = None
    ga_id = None
    set_r2 = await db.execute(
        select(Setting).where(
            Setting.user_id == camp.user_id,
            Setting.key.in_([
                "click_tracking_enabled", "api_base_url", "visitor_capture_enabled",
                "vapid_public_key", "email_capture_enabled", "facebook_pixel_id", "google_ads_id",
            ]),
        )
    )
    for s in set_r2.scalars().all():
        if s.key == "click_tracking_enabled":
            click_enabled = str(s.value or "").lower() == "true"
        elif s.key == "api_base_url":
            click_base = (s.value or "").strip().rstrip("/")
        elif s.key == "visitor_capture_enabled":
            visitor_capture = str(s.value or "").lower() == "true"
        elif s.key == "vapid_public_key" and s.value:
            vapid_public = (s.value or "").strip()
        elif s.key == "email_capture_enabled":
            email_capture = str(s.value or "").lower() == "true"
        elif s.key == "facebook_pixel_id" and s.value:
            fb_pixel = (s.value or "").strip()
        elif s.key == "google_ads_id" and s.value:
            ga_id = (s.value or "").strip()
    cta_href = aff_url_with_sub
    if click_enabled and click_base and aff_url_with_sub:
        cta_href = f"{click_base}/api/analytics/click?dw={dw.id}"

    canonical = f"https://{dom.domain}{dw.path}" if dw.path != "/" else f"https://{dom.domain}"
    # Load user settings: heatmaps, exit-intent, trust
    hotjar_id = clarity_id = None
    exit_intent = trust_elements = False
    set_r = await db.execute(
        select(Setting).where(
            Setting.user_id == camp.user_id,
            Setting.key.in_([
                "hotjar_site_id", "clarity_project_id",
                "exit_intent_enabled", "trust_elements_enabled",
            ]),
        )
    )
    for s in set_r.scalars().all():
        if s.key == "hotjar_site_id" and s.value:
            hotjar_id = s.value.strip()
        elif s.key == "clarity_project_id" and s.value:
            clarity_id = s.value.strip()
        elif s.key == "exit_intent_enabled":
            exit_intent = str(s.value or "").lower() == "true"
        elif s.key == "trust_elements_enabled":
            trust_elements = str(s.value or "").lower() == "true"

    from app.services.schema_helper import (
        build_article_schema,
        build_webpage_schema,
        build_trust_elements_html,
        build_paa_schema,
    )
    from app.services.anti_detection import get_schema_variant, _seed_from_url

    domain = dom.domain or ""
    path = (dw.path or "/").strip() or "/"
    schema_variant = get_schema_variant(domain, path, dw.id)
    title = dw.title or dom.domain
    desc = dw.meta_description or ""
    schemas = []
    if schema_variant in ("article", "both"):
        schemas.append(build_article_schema(title=title, description=desc, url=canonical))
    if schema_variant in ("webpage", "both"):
        schemas.append(build_webpage_schema(title=title, description=desc, url=canonical))
    article_schema = "".join(
        f'<script type="application/ld+json">{s}</script>' for s in schemas
    ) if schemas else ""

    seed = _seed_from_url(domain, path, dw.id)
    trust_html = build_trust_elements_html(camp.language or "ru", seed=seed) if trust_elements else None

    faq_schema = ""
    faq_block = None
    faq_qa = (dw.cloaking_rules or {}).get("faq_qa")
    if isinstance(faq_qa, list) and faq_qa:
        faq_schema = build_paa_schema(faq_qa)
        parts_faq = ['<h2>Часто спрашивают</h2>']
        for qa in faq_qa[:10]:
            q = (qa.get("question") or "").strip()
            a = (qa.get("answer") or "").strip()
            if q and a:
                parts_faq.append(
                    f'<div class="faq-item"><h3>{html.escape(q)}</h3><p>{html.escape(a)}</p></div>'
                )
        if len(parts_faq) > 1:
            faq_block = "".join(parts_faq)

    camp_settings = (camp.affiliate_rules or {}).get("settings") or {}
    cta_by_device = (dw.cloaking_rules or {}).get("cta_by_device") or camp_settings.get("cta_by_device")
    cta_desktop = None
    cta_mobile = None
    if isinstance(cta_by_device, dict):
        cta_desktop = cta_by_device.get("desktop")
        cta_mobile = cta_by_device.get("mobile")

    urgency_block = None
    u = (dw.cloaking_rules or {}).get("urgency_block") or camp_settings.get("urgency_block")
    if isinstance(u, dict) and u.get("text"):
        urgency_block = str(u["text"])
    elif isinstance(u, str) and u.strip():
        urgency_block = u.strip()

    exit_intent_title = None
    exit_intent_cta = None
    ei = (dw.cloaking_rules or {}).get("exit_intent") or camp_settings.get("exit_intent")
    if isinstance(ei, dict):
        exit_intent_title = ei.get("title") or ei.get("text")
        exit_intent_cta = ei.get("cta_text") or ei.get("cta")

    data_offers = None
    if len(offers) >= 2 and any(o.get("geo") or o.get("device") for o in offers):
        import json
        data_offers = json.dumps([{"url": o["url"], "geo": o.get("geo"), "device": o.get("device")} for o in offers])

    social_proof_block = None
    sp = (dw.cloaking_rules or {}).get("social_proof") or camp_settings.get("social_proof")
    if isinstance(sp, dict):
        parts_sp = []
        if sp.get("stats"):
            parts_sp.append(f'<div class="social-proof-stats">{sp["stats"]}</div>')
        if sp.get("text"):
            parts_sp.append(str(sp["text"]))
        if isinstance(sp.get("reviews"), list) and sp["reviews"]:
            for r in sp["reviews"][:3]:
                t = r if isinstance(r, str) else r.get("text", "")
                if t:
                    parts_sp.append(f'<div class="social-proof-review">"{t}"</div>')
        if parts_sp:
            social_proof_block = "".join(parts_sp)
    elif isinstance(sp, str) and sp.strip():
        social_proof_block = sp.strip()

    comparison_table = None
    offers_for_table = [o for o in offers if o.get("name") or o.get("rate") or o.get("amount") or o.get("term")]
    if offers_for_table:
        rows = []
        for o in offers_for_table[:5]:
            url_with_sub = _append_sub_id(o["url"], dw.id)
            name = html.escape((o.get("name") or "").strip() or "—")
            rate = html.escape((o.get("rate") or "").strip() or "—")
            amount = html.escape((o.get("amount") or "").strip() or "—")
            term = html.escape((o.get("term") or "").strip() or "—")
            link = f'<a href="{html.escape(url_with_sub)}" class="cta" rel="nofollow">Оформить</a>' if url_with_sub else "—"
            rows.append(f"<tr><td>{name}</td><td>{rate}</td><td>{amount}</td><td>{term}</td><td>{link}</td></tr>")
        comparison_table = (
            "<table><thead><tr><th>Название</th><th>Ставка</th><th>Сумма</th><th>Срок</th><th></th></tr></thead>"
            "<tbody>" + "".join(rows) + "</tbody></table>"
        )

    return render_doorway_page(
        title=title,
        meta_description=desc,
        content=dw.content or "",
        language=camp.language,
        affiliate_url=cta_href,
        canonical_url=canonical,
        hotjar_site_id=hotjar_id,
        clarity_project_id=clarity_id,
        article_schema=article_schema,
        exit_intent_enabled=exit_intent,
        trust_elements=trust_html,
        faq_schema=faq_schema or None,
        structural_seed=(domain, path, dw.id),
        cta_desktop=cta_desktop,
        cta_mobile=cta_mobile,
        comparison_table=comparison_table,
        urgency_block=urgency_block,
        social_proof_block=social_proof_block,
        exit_intent_title=exit_intent_title,
        exit_intent_cta=exit_intent_cta,
        data_offers=data_offers,
        doorway_id=dw.id,
        faq_block=faq_block,
        visitor_capture=visitor_capture and bool(click_base),
        analytics_base=click_base or "",
        push_subscribe_enabled=visitor_capture and bool(click_base) and bool(vapid_public),
        vapid_public_key=vapid_public or "",
        email_capture_enabled=email_capture and bool(click_base),
        facebook_pixel_id=fb_pixel or None,
        google_ads_id=ga_id or None,
    )
