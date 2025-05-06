import logging
import asyncio
from playwright.async_api import async_playwright

logger = logging.getLogger("src.verifications")

# Extrai conteúdo da biblioteca de anúncios do Facebook
async def extract_facebook_ads(instagram_username):
    if not instagram_username:
        return ""

    url = f"https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=BR&q={instagram_username}&search_type=keyword"
    logger.info(f"Acessando Facebook Ads Library para: {instagram_username} com Playwright")

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
            page = await context.new_page()
            await page.goto(url, timeout=60000)

            try:
                await page.locator("div[aria-label='Fechar'], div[aria-label='Close']").first.click(timeout=3000)
            except:
                pass

            await page.wait_for_timeout(3000)
            body_text = await page.inner_text("body")

            await browser.close()
            return body_text
    except Exception as e:
        logger.error(f"Erro ao acessar Facebook Ads Library com Playwright: {e}")
        return f"Erro ao extrair com Playwright: {e}"

# Extrai conteúdo da transparência de anúncios do Google
async def extract_google_ads(website):
    if not website:
        return ""

    url = f"https://adstransparency.google.com/advertiser/{website}?region=BR"
    logger.info(f"Acessando Google Ads Transparency para: {website} com Playwright")

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()
            await page.goto(url, timeout=60000)

            await page.wait_for_timeout(3000)
            body_text = await page.inner_text("body")

            await browser.close()
            return body_text
    except Exception as e:
        logger.error(f"Erro ao acessar Google Ads Transparency com Playwright: {e}")
        return f"Erro ao extrair com Playwright: {e}"

# Wrapper sincrono para chamadas externas

def extract_ads_data(platform, identifier):
    if platform == "facebook":
        return asyncio.run(extract_facebook_ads(identifier))
    elif platform == "google":
        return asyncio.run(extract_google_ads(identifier))
    else:
        return "Plataforma não suportada."
