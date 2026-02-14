"""Deploy doorway to server via SSH."""

import io
from typing import Optional

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
    offers = [{"url": o.url, "geo": o.geo, "device": o.device, "priority": o.priority, "is_active": o.is_active} for o in off_r.scalars().all()]
    aff_url = camp.affiliate_url
    if offers:
        aff_url = _get_best_offer_url(offers) or aff_url
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
    faq_qa = (dw.cloaking_rules or {}).get("faq_qa")
    if isinstance(faq_qa, list) and faq_qa:
        faq_schema = build_paa_schema(faq_qa)

    return render_doorway_page(
        title=title,
        meta_description=desc,
        content=dw.content or "",
        language=camp.language,
        affiliate_url=aff_url,
        canonical_url=canonical,
        hotjar_site_id=hotjar_id,
        clarity_project_id=clarity_id,
        article_schema=article_schema,
        exit_intent_enabled=exit_intent,
        trust_elements=trust_html,
        faq_schema=faq_schema or None,
        structural_seed=(domain, path, dw.id),
    )
