#!/usr/bin/env python3
"""
Экспорт бесплатных ключей из free-api-hunter vault в JSON для импорта в api-hub.
Читает:
  - /root/LabDoctorM/vault/free-api-hunter/secrets-backup.json
  - /root/LabDoctorM/vault/cloudflare/ (файлы *.key* и поддиректории)
  - /root/LabDoctorM/vault/free-api-hunter/*.key* если есть

Выводит JSON-массив в stdout.
Формат записи:
  {
    "provider": "cerebras",
    "key": "csk-...",
    "alias": "cerebras/apiKey.2",
    "source": "secrets-backup",
    "rate_limit_type": "requests_per_day"
  }
"""

import json
import pathlib
import sys

# Маппинг имени провайдера → тип rate limit
PROVIDER_RATE_LIMITS = {
    "cerebras": "tokens_per_minute",
    "cloudflare": "requests_per_day",
    "elevenlabs": "characters_per_month",
    "mistral": "tokens_per_minute",
    "openrouter": "requests_per_day",
    "pollinations": "unlimited",
    "ocrspace": "requests_per_month",
    "gemini": "requests_per_day",
    "cohere": "tokens_per_month",
    "manus": "credits_per_day",
    "dadata": "requests_per_day",
    "abstractapi": "requests_per_hour",
    "scraperapi": "requests_per_month",
    "pdfgeneratorapi": "requests_per_month",
    "tavily": "requests_per_month",
    "firecrawl": "requests_per_month",
    "tinyfish": "requests_per_day",
}


def sanitize_provider_name(raw: str) -> str:
    """Из 'cerebras/apiKey.2' → 'cerebras'"""
    return raw.split("/")[0].strip().lower()


def collect_from_secrets_backup(path: pathlib.Path) -> list:
    """Collect keys from secrets-backup.json (Vault seed format)"""
    results = []
    if not path.exists():
        return results
    data = json.loads(path.read_text())
    values = data.get("values", data)
    if isinstance(values, dict):
        for full_key, meta in values.items():
            if isinstance(meta, dict):
                value = meta.get("value") or meta.get("apiKey")
                if not value:
                    # Maybe it's a direct string value (old format)
                    continue
                provider = sanitize_provider_name(full_key)
                alias = full_key
                results.append({
                    "provider": provider,
                    "key": value,
                    "alias": alias,
                    "source": "secrets-backup",
                    "rate_limit_type": PROVIDER_RATE_LIMITS.get(provider, "unknown"),
                })
            elif isinstance(meta, str):
                # Direct string value
                provider = sanitize_provider_name(full_key)
                results.append({
                    "provider": provider,
                    "key": meta,
                    "alias": full_key,
                    "source": "secrets-backup",
                    "rate_limit_type": PROVIDER_RATE_LIMITS.get(provider, "unknown"),
                })
    return results


def collect_from_directory(directory: pathlib.Path) -> list:
    """Collect keys from files in vault directory"""
    results = []
    if not directory.exists():
        return results
    for item in directory.iterdir():
        if item.is_file() and ".key" in item.name:
            provider = item.name.split(".")[0]
            value = item.read_text().strip()
            results.append({
                "provider": provider,
                "key": value,
                "alias": item.name,
                "source": f"vault-file:{directory.name}",
                "rate_limit_type": PROVIDER_RATE_LIMITS.get(provider, "unknown"),
            })
        elif item.is_dir():
            # Recurse into subdirectories
            for sub in item.iterdir():
                if sub.is_file():
                    provider = item.name
                    value = sub.read_text().strip()
                    results.append({
                        "provider": provider,
                        "key": value,
                        "alias": f"{provider}/{sub.name}",
                        "source": f"vault-dir:{directory.name}/{item.name}",
                        "rate_limit_type": PROVIDER_RATE_LIMITS.get(provider, "unknown"),
                    })
    return results


def main():
    all_keys = []

    # 1. secrets-backup.json (основной источник)
    backup = pathlib.Path("/root/LabDoctorM/vault/free-api-hunter/secrets-backup.json")
    all_keys.extend(collect_from_secrets_backup(backup))

    # 2. /root/LabDoctorM/vault/cloudflare/
    cf_dir = pathlib.Path("/root/LabDoctorM/vault/cloudflare")
    all_keys.extend(collect_from_directory(cf_dir))

    # 3. /root/LabDoctorM/vault/free-api-hunter/ (файлы *.key* если есть)
    fah_dir = pathlib.Path("/root/LabDoctorM/vault/free-api-hunter")
    all_keys.extend(collect_from_directory(fah_dir))

    # Дедупликация по значению ключа
    seen = set()
    unique = []
    for k in all_keys:
        if k["key"] not in seen:
            seen.add(k["key"])
            unique.append(k)

    json.dump(unique, sys.stdout, indent=2, ensure_ascii=False)
    sys.stderr.write(f"Exported {len(unique)} unique keys (from {len(all_keys)} total)\n")


if __name__ == "__main__":
    main()
