import asyncio
import io

import imagehash
from PIL import Image


async def compare_url(page, target_url, reference_hash):
    await page.goto(
        target_url,
        {
            "waitUntil": "networkidle2",
            "timeout": 20000
        }
    )

    await asyncio.sleep(1.5)

    screenshot = await page.screenshot({
        "type": "png"
    })

    similarity = 0

    if reference_hash:
        test_hash = imagehash.phash(
            Image.open(io.BytesIO(screenshot))
        )

        similarity = int(
            (1 - ((reference_hash - test_hash) / 64.0)) * 100
        )

    return max(0, similarity), screenshot