# -*- coding: utf-8 -*-
import os
import time
import asyncio # Adicionado para Crawl4AI

# Remover importações do Selenium
# from selenium import webdriver
# from selenium.webdriver.chrome.service import Service as ChromeService
# from selenium.webdriver.common.by import By
# from selenium.webdriver.support.ui import WebDriverWait
# from selenium.webdriver.support import expected_conditions as EC
# from selenium.common.exceptions import TimeoutException, WebDriverException

# Adicionar importações do Crawl4AI
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode

from crewai import Agent, Task, Crew
import requests
from dotenv import load_dotenv
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Carregar variáveis de ambiente
load_dotenv()

# Obter chave da API OpenAI do ambiente
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    logger.warning("OPENAI_API_KEY environment variable is not set. AI analysis will fail.")
else:
    os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY

# --- Configurações do Crawl4AI ---
BROWSER_CONFIG = BrowserConfig(
    headless=True,
    browser_type="chromium", # Pode ser "firefox" ou "webkit" se preferir e estiver instalado
    viewport_width=1280,
    viewport_height=720,
    # Adicionar quaisquer outros parâmetros de browser necessários, como user_agent, proxy, etc.
    # user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36"
)

CRAWLER_RUN_CONFIG = CrawlerRunConfig(
    cache_mode=CacheMode.BYPASS, # BYPASS para sempre buscar dados frescos, ou use CACHE_FIRST/ONLY_CACHE conforme necessidade
    delay_before_return_html=8,  # Espera adicional para renderização (ajustar conforme necessário)
    magic=True,  # Ativa heurísticas automáticas de espera
    # Outras configurações como max_retries, timeout, etc.
    # timeout=60 # Timeout total para a operação de crawling
)

# --- Funções de Extração (Modificadas para Crawl4AI) ---

async def _extract_with_crawl4ai(url: str, target_name: str):
    """Função auxiliar para extrair conteúdo de uma URL usando Crawl4AI."""
    logger.info(f"Acessando {target_name} em: {url} com Crawl4AI")
    try:
        async with AsyncWebCrawler(config=BROWSER_CONFIG) as crawler:
            result = await crawler.arun(url=url, config=CRAWLER_RUN_CONFIG)
            if result.success and result.markdown:
                logger.info(f"Extração de {target_name} concluída com sucesso.")
                return result.markdown.raw_markdown
            elif result.success and not result.markdown:
                logger.warning(f"Extração de {target_name} bem-sucedida, mas sem conteúdo markdown. Retornando texto da página se disponível.")
                # Tenta pegar o texto bruto se o markdown não estiver disponível
                if result.page_content:
                    return result.page_content
                return "Erro ao extrair: Conteúdo Markdown não gerado e page_content vazio."
            else:
                error_msg = result.error_message or "Erro desconhecido durante a extração."
                logger.error(f"Falha na extração de {target_name}: {error_msg}")
                return f"Erro ao extrair: {error_msg}"
    except Exception as e:
        logger.error(f"Erro durante a extração de {target_name} para {url}: {str(e)}")
        return f"Erro ao extrair dados: {str(e)}"

def extract_facebook_ads(instagram_username):
    """Extrai o conteúdo da Biblioteca de Anúncios do Facebook para um dado usuário do Instagram usando Crawl4AI."""
    if not instagram_username:
        return ""
    url = f"https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=BR&q={instagram_username}&search_type=keyword"
    return asyncio.run(_extract_with_crawl4ai(url, f"Facebook Ads Library para {instagram_username}"))

def extract_google_ads(domain):
    """Extrai o conteúdo do Centro de Transparência de Anúncios do Google para um dado domínio usando Crawl4AI."""
    if not domain:
        return ""
    url = f"https://adstransparency.google.com/?region=BR&domain={domain}"
    return asyncio.run(_extract_with_crawl4ai(url, f"Google Ads Transparency para {domain}"))


# --- Função de Análise com IA (Mantida como original) ---

def analyze_ads_with_ai(plataforma, conteudo, consulta):
    """Analisa o conteúdo extraído usando CrewAI para determinar se há anúncios ativos."""
    if not OPENAI_API_KEY:
         logger.error("Chave API OpenAI não configurada. Análise de IA abortada.")
         return False
    if not conteudo or "Erro ao extrair" in conteudo:
        logger.warning(f"Conteúdo inválido ou erro na extração para {consulta} na plataforma {plataforma}. Análise de IA abortada.")
        return False

    try:
        logger.info(f"Iniciando análise de IA para {consulta} na plataforma {plataforma}")
        agent = Agent(
            role="Analista de Anúncios",
            goal=f"Interpretar o conteúdo da página da {plataforma} para verificar se há anúncios ativos para \'{consulta}\'.",
            backstory="Um especialista em marketing digital que analisa textos de páginas de bibliotecas de anúncios.",
            tools=[],
            verbose=False
        )

        max_content_length = 15000
        conteudo_limitado = conteudo[:max_content_length]

        if plataforma == "facebook":
            task_description = (
                f"Analise o seguinte conteúdo da Biblioteca de Anúncios do Facebook e determine se existem anúncios ATIVOS para o usuário \'{consulta}\'.\n"
                f"Conteúdo da página:\n--- INÍCIO ---\n{conteudo_limitado}\n--- FIM ---\n\n"
                f"Procure por indicadores como 'nenhum anúncio encontrado', '0 resultados', ou a presença explícita de anúncios listados. "
                f"Responda APENAS com 'Sim' se encontrar anúncios ativos, ou 'Não' caso contrário. Não inclua explicações."
            )
        else: # google
            task_description = (
                f"Analise o seguinte conteúdo do Centro de Transparência de Anúncios do Google e determine se existem anúncios ATIVOS para o domínio \'{consulta}\'.\n"
                f"Conteúdo da página:\n--- INÍCIO ---\n{conteudo_limitado}\n--- FIM ---\n\n"
                f"Procure por indicadores como 'Nenhum anúncio encontrado', 'não veiculou anúncios', ou a presença explícita de anúncios listados. "
                f"Se o texto extraído contiver a palavra 'Verificado' pelo menos uma vez próxima ao nome do domínio ou nome de empresa, considere que há anúncios ativos vinculados ao domínio analisado. "
                f"A presença da opção 'See all ads' também sugere que existem múltiplos anúncios disponíveis para navegação.\n"
                f"Elementos como filtros por período (ex: 'Qualquer horário'), localização (ex: 'Onde aparecem: Brasil') e plataformas são sempre mostrados, mas não indicam diretamente a presença de anúncios.\n"
                f"Responda APENAS com 'Sim' se encontrar anúncios ativos, ou 'Não' caso contrário. Não inclua explicações."
            )

        task = Task(
            description=task_description,
            expected_output="'Sim' ou 'Não'.",
            agent=agent
        )

        crew = Crew(
            agents=[agent],
            tasks=[task],
            verbose=False
        )

        result = crew.kickoff()
        logger.info(f"Resultado da análise de IA para {consulta} ({plataforma}): {result}")
        resposta_normalizada = str(result).strip().lower()
        return resposta_normalizada == "sim"

    except Exception as e:
        logger.error(f"Erro durante a análise de IA para {consulta} ({plataforma}): {str(e)}")
        return False

# --- Função de Verificação QSA (Mantida como original) ---

def consultar_qsa(cnpj):
    """Consulta o QSA de um CNPJ na API da ReceitaWS."""
    if not cnpj:
        return {"error": "CNPJ não fornecido"}
    try:
        cnpj_limpo = ''.join(filter(str.isdigit, cnpj))
        if len(cnpj_limpo) != 14:
             return {"error": "CNPJ inválido"}

        url = f"https://www.receitaws.com.br/v1/cnpj/{cnpj_limpo}"
        logger.info(f"Consultando QSA para CNPJ: {cnpj_limpo}")

        max_retries = 3
        delay = 60
        for attempt in range(max_retries):
            try:
                response = requests.get(url, timeout=20)
                if response.status_code == 429:
                    if attempt < max_retries - 1:
                        logger.warning(f"Rate limit atingido (429). Tentando novamente em {delay}s...")
                        time.sleep(delay)
                        delay *= 2
                    else:
                        logger.error("Rate limit atingido após múltiplas tentativas.")
                        return {"error": "Erro ao consultar API: Rate limit (429) persistente."}
                elif response.status_code == 200:
                    data = response.json()
                    logger.info(f"Consulta QSA bem-sucedida para CNPJ: {cnpj_limpo}")
                    qsa_info = {
                        "success": True,
                        "qsa": data.get("qsa", []),
                        "razao_social": data.get("nome", "N/A"),
                        "situacao": data.get("situacao", "N/A")
                    }
                    return qsa_info
                else:
                    logger.error(f"Erro na API da ReceitaWS: {response.status_code} - {response.text}")
                    return {"error": f"Erro ao consultar API: {response.status_code}"}
            except requests.exceptions.Timeout:
                 logger.error(f"Timeout na tentativa {attempt + 1} ao consultar QSA para CNPJ: {cnpj}")
                 if attempt < max_retries - 1:
                     time.sleep(5)
                 else:
                     return {"error": "Erro de conexão: Timeout persistente"}
            except requests.exceptions.RequestException as e:
                 logger.error(f"Erro na requisição QSA (tentativa {attempt + 1}) para CNPJ {cnpj}: {str(e)}")
                 if attempt < max_retries - 1:
                     time.sleep(5)
                 else:
                    return {"error": f"Erro de conexão: {str(e)}"}

        return {"error": "Erro ao consultar API após múltiplas tentativas."}

    except Exception as e:
        logger.error(f"Erro inesperado ao consultar QSA para CNPJ {cnpj}: {str(e)}")
        return {"error": f"Erro inesperado no servidor: {str(e)}"}


# --- Verificações (Adaptada para usar as novas funções de extração) ---
def run_verification_tasks(instagram_username, domain, cnpj):
    """Executa as tarefas de verificação."""
    results = {
        "instagram_username": instagram_username,
        "domain": domain,
        "cnpj": cnpj,
        "facebook_ads_status": "not_checked",
        "google_ads_status": "not_checked",
        "qsa_status": "not_checked",
        "qsa_data": None,
        "error_messages": []
    }

    # --- Verificação Facebook Ads ---
    if instagram_username:
        logger.info(f"Iniciando verificação Facebook Ads para: {instagram_username}")
        fb_content = extract_facebook_ads(instagram_username) # Agora usa Crawl4AI
        if "Erro ao extrair" in fb_content:
            results["facebook_ads_status"] = "error"
            results["error_messages"].append(f"Facebook Ads: {fb_content}")
        elif not fb_content:
             results["facebook_ads_status"] = "error"
             results["error_messages"].append(f"Facebook Ads: Conteúdo não extraído.")
        else:
            has_fb_ads = analyze_ads_with_ai("facebook", fb_content, instagram_username)
            results["facebook_ads_status"] = "active" if has_fb_ads else "inactive"
        logger.info(f"Resultado Facebook Ads para {instagram_username}: {results['facebook_ads_status']}")

    # --- Verificação Google Ads ---
    if domain:
        logger.info(f"Iniciando verificação Google Ads para: {domain}")
        google_content = extract_google_ads(domain) # Agora usa Crawl4AI
        if "Erro ao extrair" in google_content:
            results["google_ads_status"] = "error"
            results["error_messages"].append(f"Google Ads: {google_content}")
        elif not google_content:
             results["google_ads_status"] = "error"
             results["error_messages"].append(f"Google Ads: Conteúdo não extraído.")
        else:
            has_google_ads = analyze_ads_with_ai("google", google_content, domain)
            results["google_ads_status"] = "active" if has_google_ads else "inactive"
        logger.info(f"Resultado Google Ads para {domain}: {results['google_ads_status']}")

    # --- Verificação QSA ---
    if cnpj:
        logger.info(f"Iniciando verificação QSA para: {cnpj}")
        qsa_result = consultar_qsa(cnpj)
        if qsa_result.get("success"):
            results["qsa_status"] = "found"
            results["qsa_data"] = qsa_result
        else:
            results["qsa_status"] = "error"
            results["qsa_data"] = qsa_result
            results["error_messages"].append(f"QSA: {qsa_result.get('error', 'Erro desconhecido')}")
        logger.info(f"Resultado QSA para {cnpj}: {results['qsa_status']}")

    return results

# --- Bloco Principal (Exemplo de uso, se necessário para teste) ---
# if __name__ == '__main__':
#     # Exemplo de como chamar (requer .env com OPENAI_API_KEY)
#     # e instalação do crawl4ai: pip install crawl4ai
#     test_insta = "cocacola_br" # Substituir por um usuário real para teste
#     test_domain = "cocacola.com.br" # Substituir por um domínio real para teste
#     test_cnpj = "45997418000153" # CNPJ da Coca-Cola (exemplo)
#
#     print(f"Iniciando verificações para Instagram: {test_insta}, Domínio: {test_domain}, CNPJ: {test_cnpj}")
#     resultados = run_verification_tasks(test_insta, test_domain, test_cnpj)
#     print("\n--- Resultados Finais ---")
#     import json
#     print(json.dumps(resultados, indent=2, ensure_ascii=False))
#     print("------------------------")

