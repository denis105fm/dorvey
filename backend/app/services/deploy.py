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


def test_ssh_connection(
    host: str,
    port: int,
    user: str,
    auth_type: str,
    auth_data: Optional[str] = None,
) -> tuple[bool, str]:
    """Test SSH connection with given params. Returns (success, message)."""
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        connect_kw = {
            "hostname": host,
            "port": port or 22,
            "username": user,
        }
        if auth_type == "password":
            connect_kw["password"] = auth_data or ""
        else:
            key = auth_data
            if key and "\n" in key:
                pkey = paramiko.RSAKey.from_private_key(io.StringIO(key))
            elif key:
                pkey = paramiko.RSAKey.from_private_key_file(key)
            else:
                pkey = None
            if pkey:
                connect_kw["pkey"] = pkey
            elif auth_type == "password":
                connect_kw["password"] = ""
        client.connect(**connect_kw, timeout=10)
        client.close()
        return True, "Подключение успешно"
    except Exception as e:
        return False, str(e)


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


def _get_ssh_client_from_params(
    host: str,
    port: int,
    user: str,
    auth_type: str,
    auth_data: Optional[str],
) -> paramiko.SSHClient:
    """Build SSH client from raw params (for use in background tasks)."""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    connect_kw = {
        "hostname": host,
        "port": port or 22,
        "username": user,
    }
    if auth_type == "password":
        connect_kw["password"] = auth_data or ""
    else:
        key = auth_data
        if key and "\n" in key:
            pkey = paramiko.RSAKey.from_private_key(io.StringIO(key))
        elif key:
            pkey = paramiko.RSAKey.from_private_key_file(key)
        else:
            pkey = None
        if pkey:
            connect_kw["pkey"] = pkey
        else:
            connect_kw["password"] = ""
    client.connect(**connect_kw)
    return client


def deploy_sitemap_robots_sync(
    host: str,
    port: int,
    user: str,
    auth_type: str,
    auth_data: Optional[str],
    base_path: str,
    sitemap_xml: str,
    robots_txt: str,
) -> tuple[bool, str]:
    """Upload sitemap.xml and robots.txt to server web root. Returns (success, message)."""
    try:
        client = _get_ssh_client_from_params(host, port, user, auth_type, auth_data)
        sftp = client.open_sftp()
        root = (base_path or "/var/www/html").rstrip("/")
        for name, content in [("sitemap.xml", sitemap_xml), ("robots.txt", robots_txt)]:
            remote = f"{root}/{name}"
            buf = io.BytesIO(content.encode("utf-8"))
            sftp.putfo(buf, remote)
        sftp.close()
        client.close()
        return True, f"sitemap.xml and robots.txt deployed to {root}"
    except Exception as e:
        return False, str(e)


def deploy_indexnow_key_sync(
    host: str,
    port: int,
    user: str,
    auth_type: str,
    auth_data: Optional[str],
    base_path: str,
    key: str,
) -> tuple[bool, str]:
    """Upload IndexNow key file {key}.txt to server web root. Returns (success, message)."""
    if not key or len(key) < 8:
        return False, "IndexNow key missing or too short"
    try:
        client = _get_ssh_client_from_params(host, port, user, auth_type, auth_data)
        sftp = client.open_sftp()
        root = (base_path or "/var/www/html").rstrip("/")
        remote = f"{root}/{key}.txt"
        buf = io.BytesIO(key.encode("utf-8"))
        sftp.putfo(buf, remote)
        sftp.close()
        client.close()
        return True, f"{key}.txt deployed to {root}"
    except Exception as e:
        return False, str(e)


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
    remote_suffix: str = "",
) -> tuple[bool, str]:
    """
    Upload HTML to server. Returns (success, message).
    Path like / or /page1 - becomes index.html or page1/index.html.
    remote_suffix: e.g. ".seo" -> index.seo.html (for cloaking bot version).
    """
    try:
        client = _get_ssh_client(server)
        sftp = client.open_sftp()
        root = (base_path or server.path or "/var/www/html").rstrip("/")
        idx = f"index{remote_suffix}.html" if remote_suffix else "index.html"
        if path in ("", "/"):
            remote = f"{root}/{idx}"
        else:
            clean = path.strip("/")
            remote = f"{root}/{clean}/{idx}"
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


def deploy_root_index_redirect(
    server: Server,
    first_path: str,
    base_path: str = "/var/www/html",
) -> tuple[bool, str]:
    """
    Deploy a minimal index.html at server root that redirects to first_path.
    Use when no doorway has path "/" so that opening the domain root doesn't return 404.
    first_path: e.g. "/en/survey-sites" (must start with /).
    """
    path = (first_path or "/").strip()
    if not path.startswith("/"):
        path = "/" + path
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta http-equiv="refresh" content="0;url={path}">
<title>Redirect</title>
</head>
<body><p>Redirecting...</p></body>
</html>"""
    return deploy_doorway_sync(server, "", "/", html, base_path or getattr(server, "path", None) or "/var/www/html")


def remove_doorway_from_server(
    server: Server,
    path: str,
    base_path: str = "/var/www/html",
) -> tuple[bool, str]:
    """
    Remove doorway files from server (index.html and optional index.seo.html).
    When path is / we remove root index; when path is /slug we remove slug/index.html and optionally the directory.
    Returns (success, message). Errors (e.g. file not found) are logged but not fatal — returns True if at least one remove succeeded or nothing was there.
    """
    path = (path or "/").strip() or "/"
    root = (base_path or getattr(server, "path", None) or "/var/www/html").rstrip("/")
    if getattr(server, "auth_type", None) == "ftp":
        return _remove_doorway_ftp(
            host=server.host,
            user=server.user,
            password=server.auth_data or "",
            path=path,
            remote_path=root,
            port=server.port or 21,
        )
    return _remove_doorway_ssh(server, path, root)


def _remove_doorway_ssh(server: Server, path: str, root: str) -> tuple[bool, str]:
    """Remove index.html and index.seo.html via SFTP, then rmdir path if not root."""
    try:
        client = _get_ssh_client(server)
        sftp = client.open_sftp()
        removed = []
        for suffix in ("", ".seo"):
            idx = f"index{suffix}.html" if suffix else "index.html"
            if path in ("", "/"):
                remote = f"{root}/{idx}"
            else:
                clean = path.strip("/")
                remote = f"{root}/{clean}/{idx}"
            try:
                sftp.remove(remote)
                removed.append(remote)
            except FileNotFoundError:
                pass
            except OSError as e:
                if "No such file" not in str(e):
                    pass  # ignore
        if path not in ("", "/"):
            clean = path.strip("/")
            dir_path = f"{root}/{clean}"
            try:
                sftp.rmdir(dir_path)
                removed.append(dir_path)
            except (OSError, FileNotFoundError):
                pass  # dir not empty or missing
        sftp.close()
        client.close()
        return True, f"Removed from server: {', '.join(removed) or 'nothing was deployed'}"
    except Exception as e:
        return False, str(e)


def _remove_doorway_ftp(
    host: str,
    user: str,
    password: str,
    path: str,
    remote_path: str = "/",
    port: int = 21,
) -> tuple[bool, str]:
    """Remove index.html via FTP."""
    try:
        from ftplib import FTP
        ftp = FTP()
        ftp.connect(host, port)
        ftp.login(user, password)
        root = remote_path.rstrip("/")
        if path in ("", "/"):
            ftp.cwd(root)
            fname = "index.html"
        else:
            clean = path.strip("/")
            ftp.cwd(f"{root}/{clean}")
            fname = "index.html"
        try:
            ftp.delete(fname)
            msg = f"Removed {fname}"
        except Exception as e:
            if "550" in str(e) or "not found" in str(e).lower():
                msg = "File was not on server"
            else:
                raise
        ftp.quit()
        return True, msg
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
    # Оставляем только hostname (без протокола и пути)
    domain_clean = (domain or "").strip().lower()
    for p in ("https://", "http://"):
        if domain_clean.startswith(p):
            domain_clean = domain_clean[len(p):]
    if "/" in domain_clean:
        domain_clean = domain_clean.split("/")[0]
    domain_clean = domain_clean.rstrip("/").split(":")[0]  # убрать порт
    if not domain_clean or domain_clean == "localhost":
        return False, "Invalid domain for SSL"
    try:
        client = _get_ssh_client(server)
        cmd = (
            f"certbot certonly --webroot -w {webroot} -d {domain_clean} "
            "--non-interactive --agree-tos --register-unsafely-without-email "
            "2>&1 || true"
        )
        stdin, stdout, stderr = client.exec_command(cmd, timeout=120)
        out = (stdout.read().decode() or "") + (stderr.read().decode() or "")
        client.close()
        ok = "Successfully received certificate" in out or "Certificate not yet due for renewal" in out
        if ok:
            # Пытаемся настроить nginx на 443, чтобы HTTPS заработал
            nginx_msg = _configure_nginx_443(client_factory=lambda: _get_ssh_client(server), domain=domain_clean, webroot=webroot)
            if nginx_msg:
                out = out.rstrip() + "\n" + nginx_msg
        return ok, out or "OK"
    except Exception as e:
        return False, str(e)


def _configure_nginx_443(client_factory, domain: str, webroot: str) -> str:
    """После успешного certbot создаём конфиг nginx для listen 443 и перезагружаем nginx. Возвращает сообщение для лога."""
    import base64
    config = f"""server {{
  listen 443 ssl;
  server_name {domain};
  ssl_certificate /etc/letsencrypt/live/{domain}/fullchain.pem;
  ssl_certificate_key /etc/letsencrypt/live/{domain}/privkey.pem;
  root {webroot.rstrip('/')};
  index index.html;
  location / {{
    try_files $uri $uri/ $uri/index.html =404;
  }}
}}
"""
    safe_name = domain.replace(".", "_")
    try:
        client = client_factory()
        b64 = base64.b64encode(config.encode()).decode()
        # Записываем через base64, чтобы не ломать кавычки в shell
        cmd = f"echo '{b64}' | base64 -d > /etc/nginx/conf.d/dorvey-ssl-{safe_name}.conf 2>/dev/null && nginx -t 2>&1 && (systemctl reload nginx 2>/dev/null || service nginx reload 2>/dev/null) && echo 'Nginx HTTPS configured' || echo 'Nginx: write/reload failed (check permissions)'"
        stdin, stdout, stderr = client.exec_command(cmd, timeout=15)
        out = (stdout.read().decode() or "") + (stderr.read().decode() or "")
        client.close()
        return out.strip() if out else ""
    except Exception as e:
        return f"Nginx config skip: {e}"


def _append_sub_id(url: str, doorway_id: int, offer_id: Optional[int] = None, source: Optional[str] = None) -> str:
    """Add sub_id to affiliate URL for postback attribution.
    If offer_id is set: sub_id=doorway_id_offer_id (for per-offer metrics).
    If source is set: append _source (e.g. doorway_id_offer_id_google).
    Otherwise: sub_id=doorway_id (backward compatible).
    Supports placeholders {sub_id}, {doorway_id}.
    """
    if not url or doorway_id <= 0:
        return url
    if offer_id is not None and offer_id > 0:
        sid = f"{doorway_id}_{offer_id}"
    else:
        sid = str(doorway_id)
    if source and len(source) <= 32 and source.replace("_", "").replace("-", "").isalnum():
        sid = f"{sid}_{source}"
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
    """Pick best offer by priority and geo/device. Returns URL or None."""
    if not offers:
        return None
    for o in sorted(offers, key=lambda x: -(x.get("priority") or 0)):
        if not o.get("is_active", True):
            continue
        og, od = o.get("geo"), o.get("device")
        if geo and og and geo.upper() != og.upper():
            continue
        if device and od and device.lower() != od.lower():
            continue
        return o.get("url")
    return offers[0].get("url") if offers else None


def _cold_start_offer_score(o: dict) -> tuple[float, int]:
    """
    Скор для приоритета оффера при нулевых данных (холодный старт).
    Учитываем: приоритет оффера, парсим rate (выплата) как число.
    """
    priority = int(o.get("priority") or 0)
    rate_val = 0.0
    try:
        r = (o.get("rate") or "").strip().replace("$", "").replace(",", ".").replace(" ", "")
        if r:
            rate_val = float(r)
    except (ValueError, TypeError):
        pass
    return (rate_val * 0.1 + priority, priority)


async def get_best_offer_url_by_roi(
    db: AsyncSession,
    offers: list,
    geo: Optional[str] = None,
    device: Optional[str] = None,
    days: int = 30,
) -> tuple[Optional[str], Optional[int]]:
    """
    Pick best offer by ROI (revenue/clicks) when we have enough data, else by priority.
    offers must have keys: id, url, geo, device, priority, is_active.
    Returns (url, offer_id) or (None, None).
    """
    from datetime import datetime, timedelta
    from sqlalchemy import func

    from app.models.offer_metrics import OfferMetrics

    if not offers:
        return None, None
    filtered = []
    for o in offers:
        if not o.get("is_active", True):
            continue
        og, od = o.get("geo"), o.get("device")
        if geo and og and geo.upper() != og.upper():
            continue
        if device and od and device.lower() != od.lower():
            continue
        filtered.append(o)
    if not filtered:
        return None, None

    since = datetime.utcnow() - timedelta(days=days)
    offer_ids = [o["id"] for o in filtered if o.get("id")]
    if not offer_ids:
        best = max(filtered, key=lambda x: (x.get("priority") or 0))
        return best.get("url"), best.get("id")

    r = await db.execute(
        select(
            OfferMetrics.offer_id,
            func.coalesce(func.sum(OfferMetrics.clicks), 0).label("clk"),
            func.coalesce(func.sum(OfferMetrics.revenue), 0).label("rev"),
        )
        .where(OfferMetrics.offer_id.in_(offer_ids), OfferMetrics.date >= since)
        .group_by(OfferMetrics.offer_id)
    )
    rows = {row.offer_id: (int(row.clk or 0), float(row.rev or 0)) for row in r.all()}

    has_any_clicks = any(clk >= 5 for clk, _ in rows.values()) if rows else False
    if not has_any_clicks:
        # Приоритет офферов при нуле: холодный старт по score (rate, priority, качество)
        best = max(filtered, key=lambda o: _cold_start_offer_score(o))
        return best.get("url"), best.get("id")

    def roi(o):
        oid = o.get("id")
        clk, rev = rows.get(oid, (0, 0))
        if clk >= 5:
            return (rev / clk if clk else 0, clk, o.get("priority") or 0)
        return (-1, clk, o.get("priority") or 0)

    best = max(filtered, key=roi)
    return best.get("url"), best.get("id")


async def prepare_doorway_html(db: AsyncSession, doorway_id: int, for_bot: bool = False) -> Optional[str]:
    """Load doorway and campaign/domain, return full HTML.
    for_bot=True: SEO version for crawlers (no exit-intent, no pop-ups, no tracking scripts).
    """
    r = await db.execute(
        select(Doorway, Domain, Server)
        .join(Domain, Doorway.domain_id == Domain.id)
        .outerjoin(Server, Domain.server_id == Server.id)
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
    offers = [{"id": o.id, "url": o.url, "name": o.name, "rate": o.rate, "amount": o.amount, "term": o.term, "geo": o.geo, "device": o.device, "priority": o.priority, "is_active": o.is_active} for o in offers_raw]
    aff_url = camp.affiliate_url
    best_offer_id = None
    if offers:
        aff_url_candidate, best_offer_id = await get_best_offer_url_by_roi(db, offers, None, None)
        if aff_url_candidate:
            aff_url = aff_url_candidate
        else:
            aff_url = _get_best_offer_url(offers) or aff_url
            best_offer_id = next((o["id"] for o in offers if o.get("url") == aff_url), None)
    aff_url_with_sub = _append_sub_id(aff_url, dw.id, best_offer_id) if aff_url else None

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
        if best_offer_id:
            cta_href += f"&oid={best_offer_id}"

    canonical = f"https://{dom.domain}{dw.path}" if dw.path != "/" else f"https://{dom.domain}"
    d_clean = (dom.domain or "").replace("https://", "").replace("http://", "").strip().rstrip("/")
    og_image_url = f"https://{d_clean}/og-image.jpg" if d_clean else None
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
        get_urgency_preset,
        get_social_proof_preset,
        get_exit_intent_preset,
        get_cta_preset,
        get_doorway_ui_strings,
    )
    from app.services.dataforseo_service import get_language_code
    from app.services.anti_detection import get_schema_variant, _seed_from_url
    from app.services.seo_tools import get_internal_links_suggestions

    domain = dom.domain or ""
    path = (dw.path or "/").strip() or "/"
    schema_variant = get_schema_variant(domain, path, dw.id)
    if for_bot and getattr(camp, "is_black", False):
        schema_variant = "webpage"  # один тип схемы — меньше паттерн для детекта
    title = dw.title or dom.domain
    desc = dw.meta_description or ""
    schemas = []
    if schema_variant in ("article", "both"):
        date_pub = None
        if getattr(dw, "deployed_at", None):
            date_pub = dw.deployed_at.isoformat() if hasattr(dw.deployed_at, "isoformat") else str(dw.deployed_at)
        elif getattr(dw, "created_at", None):
            date_pub = dw.created_at.isoformat() if hasattr(dw.created_at, "isoformat") else str(dw.created_at)
        schemas.append(build_article_schema(title=title, description=desc, url=canonical, date_published=date_pub))
    if schema_variant in ("webpage", "both"):
        schemas.append(build_webpage_schema(title=title, description=desc, url=canonical))
    article_schema = "".join(
        f'<script type="application/ld+json">{s}</script>' for s in schemas
    ) if schemas else ""

    seed = _seed_from_url(domain, path, dw.id)
    camp_lang = (
        get_language_code(dw.target_geo) if getattr(dw, "target_geo", None) else (camp.language or "en")
    )
    ui = get_doorway_ui_strings(camp_lang)
    trust_html = build_trust_elements_html(camp_lang, seed=seed) if trust_elements else None

    faq_schema = ""
    faq_block = None
    faq_qa = (dw.cloaking_rules or {}).get("faq_qa")
    if isinstance(faq_qa, list) and faq_qa:
        faq_schema = build_paa_schema(faq_qa)
        faq_heading = ui.get("faq_heading", "Frequently asked questions")
        parts_faq = [f'<h2>{html.escape(faq_heading)}</h2>']
        for qa in faq_qa[:10]:
            q = (qa.get("question") or "").strip()
            a = (qa.get("answer") or "").strip()
            if q and a:
                parts_faq.append(
                    f'<div class="faq-item"><h3>{html.escape(q)}</h3><p>{html.escape(a)}</p></div>'
                )
        if len(parts_faq) > 1:
            faq_block = "".join(parts_faq)

    internal_links = await get_internal_links_suggestions(db, doorway_id, camp.id, max_links=3)
    internal_links_block = None
    if internal_links and not (for_bot and getattr(camp, "is_black", False)):
        il_heading = ui.get("internal_links_heading", "Related topics")
        parts_il = [f'<h2>{html.escape(il_heading)}</h2><ul class="internal-links-list">']
        for link in internal_links:
            url_esc = html.escape(link.get("url") or "")
            title_esc = html.escape(link.get("title") or link.get("anchor") or "")
            if url_esc and title_esc:
                parts_il.append(f'<li><a href="{url_esc}" rel="internal">{title_esc}</a></li>')
        if len(parts_il) > 1:
            parts_il.append("</ul>")
            internal_links_block = '<div class="internal-links">' + "".join(parts_il) + "</div>"

    camp_settings = (camp.affiliate_rules or {}).get("settings") or {}
    cta_by_device = (dw.cloaking_rules or {}).get("cta_by_device") or camp_settings.get("cta_by_device")
    cta_desktop = None
    cta_mobile = None
    if isinstance(cta_by_device, dict):
        cta_desktop = cta_by_device.get("desktop")
        cta_mobile = cta_by_device.get("mobile")
    if (not cta_desktop and not cta_mobile) and not for_bot:
        preset = get_cta_preset(camp_lang, seed)
        cta_desktop = preset.get("desktop") or ui.get("default_cta", "Learn more")
        cta_mobile = preset.get("mobile") or cta_desktop

    urgency_block = None
    u = (dw.cloaking_rules or {}).get("urgency_block") or camp_settings.get("urgency_block")
    if isinstance(u, dict) and u.get("text"):
        urgency_block = str(u["text"])
    elif isinstance(u, str) and u.strip():
        urgency_block = u.strip()
    if not urgency_block and not for_bot:
        urgency_block = get_urgency_preset(camp_lang, seed)

    exit_intent_title = None
    exit_intent_cta = None
    ei = (dw.cloaking_rules or {}).get("exit_intent") or camp_settings.get("exit_intent")
    if isinstance(ei, dict):
        exit_intent_title = ei.get("title") or ei.get("text")
        exit_intent_cta = ei.get("cta_text") or ei.get("cta")
    if (not exit_intent_title and not exit_intent_cta) and not for_bot and exit_intent:
        preset = get_exit_intent_preset(camp_lang, seed)
        exit_intent_title = preset.get("title")
        exit_intent_cta = preset.get("cta")

    data_offers = None
    if len(offers) >= 2 and any(o.get("geo") or o.get("device") for o in offers):
        import json
        data_offers = json.dumps([{"id": o.get("id"), "url": o["url"], "geo": o.get("geo"), "device": o.get("device")} for o in offers])

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
    if not social_proof_block and not for_bot:
        preset = get_social_proof_preset(camp_lang, seed)
        parts_sp = []
        if preset.get("stats"):
            parts_sp.append(f'<div class="social-proof-stats">{preset["stats"]}</div>')
        for r in preset.get("reviews") or []:
            t = r if isinstance(r, str) else r.get("text", "")
            if t:
                parts_sp.append(f'<div class="social-proof-review">"{t}"</div>')
        if parts_sp:
            social_proof_block = "".join(parts_sp)

    comparison_table = None
    camp_show_table = camp_settings.get("show_offers_table", False)
    offers_for_table = [o for o in offers if o.get("name") or o.get("rate") or o.get("amount") or o.get("term")]
    if not offers_for_table and offers:
        offers_for_table = [dict(o, name=o.get("name") or f"{ui.get('option_label', 'Option')} {i+1}") for i, o in enumerate(offers[:5])]
    if camp_show_table and offers_for_table:
        n_h, r_h, a_h, t_h, apply_t = (
            ui.get("table_name", "Name"),
            ui.get("table_rate", "Rate"),
            ui.get("table_amount", "Amount"),
            ui.get("table_term", "Term"),
            ui.get("table_apply", "Apply"),
        )
        rows = []
        for o in offers_for_table[:5]:
            url_with_sub = _append_sub_id(o["url"], dw.id, o.get("id"))
            name = html.escape((o.get("name") or "").strip() or "—")
            rate = html.escape((o.get("rate") or "").strip() or "—")
            amount = html.escape((o.get("amount") or "").strip() or "—")
            term = html.escape((o.get("term") or "").strip() or "—")
            link = f'<a href="{html.escape(url_with_sub)}" class="cta" rel="nofollow">{html.escape(apply_t)}</a>' if url_with_sub else "—"
            rows.append(f"<tr><td>{name}</td><td>{rate}</td><td>{amount}</td><td>{term}</td><td>{link}</td></tr>")
        comparison_table = (
            f"<table><thead><tr><th>{html.escape(n_h)}</th><th>{html.escape(r_h)}</th><th>{html.escape(a_h)}</th><th>{html.escape(t_h)}</th><th></th></tr></thead>"
            "<tbody>" + "".join(rows) + "</tbody></table>"
        )

    quiz_block = None
    quiz_data = (dw.cloaking_rules or {}).get("quiz")
    if not for_bot and isinstance(quiz_data, dict) and quiz_data.get("enabled") and quiz_data.get("questions"):
        import json as _json
        questions = quiz_data["questions"]
        if isinstance(questions, list) and len(questions) >= 1:
            q_title = html.escape(ui.get("quiz_title", "Find the right option for you"))
            q_next = html.escape(ui.get("quiz_next", "Next"))
            q_submit = html.escape(ui.get("quiz_submit", "Go to offer"))
            cta_esc = html.escape(cta_href or "")
            safe_questions = []
            for q in questions[:8]:
                if isinstance(q, dict) and q.get("question") and isinstance(q.get("options"), list):
                    safe_questions.append({"question": str(q["question"])[:120], "options": [str(o)[:60] for o in q["options"][:4]]})
            if safe_questions:
                data_questions_json = _json.dumps(safe_questions, ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e")
                data_questions_esc = html.escape(data_questions_json)
                quiz_block = f'''<div id="dv-quiz" class="dv-quiz" data-questions="{data_questions_esc}" data-cta-url="{cta_esc}" data-title="{q_title}" data-submit="{q_submit}"><h2>{q_title}</h2><div class="dv-quiz-question"><p id="dv-quiz-q"></p><div class="dv-quiz-options" id="dv-quiz-opts"></div><div class="dv-quiz-nav"><a id="dv-quiz-cta" href="{cta_esc}" class="cta" rel="nofollow" style="display:none">{q_submit}</a></div></div></div><script>(function(){{var el=document.getElementById("dv-quiz");if(!el)return;var q=JSON.parse(el.getAttribute("data-questions"));var idx=0;var qEl=document.getElementById("dv-quiz-q");var optsEl=document.getElementById("dv-quiz-opts");var ctaLink=document.getElementById("dv-quiz-cta");function show(){{if(idx>=q.length){{optsEl.innerHTML="";ctaLink.style.display="inline-block";return;}}var item=q[idx];qEl.textContent=item.question;optsEl.innerHTML="";item.options.forEach(function(opt){{var b=document.createElement("button");b.type="button";b.textContent=opt;b.onclick=function(){{idx++;show();}};optsEl.appendChild(b);}});}}show();}})();</script>'''

    content_for_render = dw.content or ""
    if for_bot:
        seo_tail = (dw.cloaking_rules or {}).get("seo_tail")
        if isinstance(seo_tail, str) and seo_tail.strip():
            tail_esc = seo_tail.strip()[:500].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            content_for_render = content_for_render + (
                '<div class="dv-related-topics" style="margin-top:2rem;padding-top:1rem;border-top:1px solid #e5e7eb;'
                'font-size:0.7rem;line-height:1.5;color:#94a3b8;">'
                f'{tail_esc}</div>'
            )

    if for_bot:
        hotjar_id = clarity_id = fb_pixel = ga_id = None
        exit_intent = False
        visitor_capture = False
        data_offers = None

    return render_doorway_page(
        title=title,
        meta_description=desc,
        content=content_for_render,
        language=camp_lang,
        affiliate_url=cta_href,
        canonical_url=canonical,
        hotjar_site_id=None if for_bot else hotjar_id,
        clarity_project_id=None if for_bot else clarity_id,
        article_schema=article_schema,
        exit_intent_enabled=False if for_bot else exit_intent,
        trust_elements=trust_html,
        faq_schema=faq_schema or None,
        structural_seed=(domain, path, dw.id),
        layout_index_override=getattr(dw, "layout_index", None),
        cta_desktop=cta_desktop,
        cta_mobile=cta_mobile,
        comparison_table=comparison_table,
        urgency_block=urgency_block,
        social_proof_block=social_proof_block,
        exit_intent_title=exit_intent_title,
        exit_intent_cta=exit_intent_cta,
        data_offers=None if for_bot else data_offers,
        doorway_id=dw.id,
        faq_block=faq_block,
        internal_links_block=internal_links_block,
        quiz_block=quiz_block,
        visitor_capture=False if for_bot else (visitor_capture and bool(click_base)),
        analytics_base=click_base or "",
        push_subscribe_enabled=False if for_bot else (visitor_capture and bool(click_base) and bool(vapid_public)),
        vapid_public_key=vapid_public or "",
        email_capture_enabled=False if for_bot else (email_capture and bool(click_base)),
        facebook_pixel_id=None if for_bot else fb_pixel,
        google_ads_id=None if for_bot else ga_id,
        og_image_url=og_image_url,
    )
