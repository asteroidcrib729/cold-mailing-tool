"""Bounded domain record diagnostics: presence is not validity or deliverability."""

import dns.resolver


def txt_status(domain: str, prefix: str) -> str:
    try:
        records = dns.resolver.resolve(domain, "TXT", lifetime=5)
        return (
            "present"
            if any(b"".join(row.strings).decode().lower().startswith(prefix) for row in records)
            else "missing"
        )
    except dns.resolver.NXDOMAIN, dns.resolver.NoAnswer:
        return "missing"
    except Exception:
        return "unknown"


def domain_health(domain: str) -> dict[str, str]:
    return {
        "spf": txt_status(domain, "v=spf1"),
        "dmarc": txt_status("_dmarc." + domain, "v=dmarc1"),
    }
