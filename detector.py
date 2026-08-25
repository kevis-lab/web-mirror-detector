from urllib.parse import urlparse
import re


def generate_candidate_urls(
    ref_url,
    start_num,
    end_num,
    extra_tlds,
    prefix_active,
    suffix_active
):
    parsed = urlparse(ref_url).hostname or ref_url
    clean_hostname = parsed.replace("www.", "")
    base_name = re.sub(r'\d+', '', clean_hostname.split('.')[0])

    raw_domains = []

    for tld in set(extra_tlds):
        raw_domains.append(f"{base_name}.{tld}")

        for i in range(start_num, end_num + 1):
            if prefix_active:
                raw_domains.append(f"{i}{base_name}.{tld}")

            if suffix_active:
                raw_domains.append(f"{base_name}{i}.{tld}")

            if prefix_active and suffix_active:
                if end_num > 50:
                    continue

                for j in range(start_num, end_num + 1):
                    raw_domains.append(f"{i}{base_name}{j}.{tld}")

    urls_to_check = []

    for domain in set(raw_domains):
        urls_to_check.append(f"https://{domain}")
        urls_to_check.append(f"https://www.{domain}")

    urls_to_check = list(set(urls_to_check))

    ref_host = urlparse(ref_url).hostname
    urls_to_check = [
        url for url in urls_to_check
        if urlparse(url).hostname != ref_host
    ]

    return urls_to_check