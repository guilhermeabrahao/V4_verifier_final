# -*- coding: utf-8 -*-
import os
import time
import threading
from playwright.sync_api import sync_playwright
from crewai import Agent, Task, Crew
import requests
from dotenv import load_dotenv
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Carregar variáveis de ambiente
load_dotenv()

# Obter chave da API OpenAI do ambiente
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    logger.warning("OPENAI_API_KEY environment variable is not set. AI analysis will fail.")
else:
    os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY

# --- Funções de Extração --- 

def extract_facebook_ads(instagram_username):
    """Extrai o conteúdo da Biblioteca de Anúncios do Facebook para um dado usuário do Instagram."""
    if not instagram_username:
        return ""
    try:
        url = f"https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=BR&q={instagram_username}&search_type=keyword"
        logger.info(f"Acessando Facebook Ads Library para: {instagram_username}")
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, timeout=60000) # Timeout aumentado para 60s
            # Esperar por um seletor que indique que a página carregou (ajustar se necessário)
            page.wait_for_selector("text=Resultados", timeout=30000) 
            page.wait_for_timeout(2000) # Espera adicional para garantir carregamento dinâmico
            text = page.inner_text("body")
            browser.close()
            logger.info(f"Extração da Facebook Ads Library concluída para: {instagram_username}")
            return text
    except Exception as e:
        logger.error(f"Erro ao extrair anúncios do Facebook para {instagram_username}: {str(e)}")
        return f"Erro ao extrair: {str(e)}" # Retorna a mensagem de erro para depuração

def extract_google_ads(domain):
    """Extrai o conteúdo do Centro de Transparência de Anúncios do Google para um dado domínio."""
    if not domain:
        return ""
    try:
        url = f"https://adstransparency.google.com/?region=BR&domain={domain}"
        logger.info(f"Acessando Google Ads Transparency para: {domain}")
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, timeout=60000) # Timeout aumentado para 60s
             # Esperar por um seletor que indique que a página carregou (ajustar se necessário)
            page.wait_for_selector("text=Princípios", timeout=30000)
            page.wait_for_timeout(2000) # Espera adicional
            text = page.inner_text("body")
            browser.close()
            logger.info(f"Extração do Google Ads Transparency concluída para: {domain}")
            return text
    except Exception as e:
        logger.error(f"Erro ao extrair anúncios do Google para {domain}: {str(e)}")
        return f"Erro ao extrair: {str(e)}" # Retorna a mensagem de erro para depuração

# --- Função de Análise com IA --- 

def analyze_ads_with_ai(plataforma, conteudo, consulta):
    """Analisa o conteúdo extraído usando CrewAI para determinar se há anúncios ativos."""
    if not OPENAI_API_KEY:
         logger.error("Chave API OpenAI não configurada. Análise de IA abortada.")
         return False # Ou algum indicativo de erro
    if not conteudo or "Erro ao extrair" in conteudo:
        logger.warning(f"Conteúdo inválido ou erro na extração para {consulta} na plataforma {plataforma}. Análise de IA abortada.")
        return False # Não analisar se houve erro na extração

    try:
        logger.info(f"Iniciando análise de IA para {consulta} na plataforma {plataforma}")
        agent = Agent(
            role="Analista de Anúncios",
            goal=f"Interpretar o conteúdo da página da {plataforma} para verificar se há anúncios ativos para '{consulta}'.",
            backstory="Um especialista em marketing digital que analisa textos de páginas de bibliotecas de anúncios.",
            tools=[],
            verbose=False # Reduzir verbosidade no log de produção
        )

        if plataforma == "facebook":
            task_description = (
                f"Analise o seguinte conteúdo da Biblioteca de Anúncios do Facebook e determine se existem anúncios ATIVOS para o usuário '{consulta}'. \n"
                f"Conteúdo da página:\n--- INÍCIO ---\n{conteudo[:15000]}\n--- FIM ---\n\n"
                f"Procure por indicadores como 'nenhum anúncio encontrado', '0 resultados', ou a presença explícita de anúncios listados. "
                f"Responda APENAS com 'Sim' se encontrar anúncios ativos, ou 'Não' caso contrário. Não inclua explicações."
            )
        else: # google
            task_description = (
                f"Analise o seguinte conteúdo do Centro de Transparência de Anúncios do Google e determine se existem anúncios ATIVOS para o domínio '{consulta}'. \n"
                f"Conteúdo da página:\n--- INÍCIO ---\n{conteudo[:15000]}\n--- FIM ---\n\n"
                f"Procure por indicadores como 'Nenhum anúncio encontrado', 'não veiculou anúncios', ou a presença explícita de anúncios listados. "
                f"Se o texto extraído contiver a palavra 'Verificado' pelo menos uma vez próxima ao nome do domínio ou nome de empresa, considere que há anúncios ativos vinculados ao domínio analisado. "
                f"A presença da opção 'See all ads' também sugere que existem múltiplos anúncios disponíveis para navegação."
                f"Elementos como filtros por período (ex: 'Qualquer horário'), localização (ex: 'Onde aparecem: Brasil') e plataformas são sempre mostrados, mas não indicam diretamente a presença de anúncios."
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
        # Normaliza a resposta para garantir que seja 'sim' ou 'nao'
        resposta_normalizada = str(result).strip().lower()
        return resposta_normalizada == "sim"

    except Exception as e:
        logger.error(f"Erro durante a análise de IA para {consulta} ({plataforma}): {str(e)}")
        return False # Retorna False em caso de erro na IA

# --- Função de Verificação QSA --- 

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
        
        # Tentar até 3 vezes com espera exponencial em caso de rate limit (429)
        max_retries = 3
        delay = 60 # segundos
        for attempt in range(max_retries):
            response = requests.get(url, timeout=20) # Timeout de 20s
            if response.status_code == 429:
                if attempt < max_retries - 1:
                    logger.warning(f"Rate limit atingido (429). Tentando novamente em {delay}s...")
                    time.sleep(delay)
                    delay *= 2 # Backoff exponencial
                else:
                    logger.error("Rate limit atingido após múltiplas tentativas.")
                    return {"error": "Erro ao consultar API: Rate limit (429) persistente."}
            elif response.status_code == 200:
                data = response.json()
                logger.info(f"Consulta QSA bem-sucedida para CNPJ: {cnpj_limpo}")
                qsa_info = {
                    "success": True,
                    "qsa": data.get("qsa", []), # Retorna lista vazia se não houver QSA
                    "razao_social": data.get("nome", "N/A"),
                    "situacao": data.get("situacao", "N/A")
                }
                return qsa_info
            else:
                logger.error(f"Erro na API da ReceitaWS: {response.status_code} - {response.text}")
                return {"error": f"Erro ao consultar API: {response.status_code}"}
        
        # Caso esgote as tentativas de rate limit
        return {"error": "Erro ao consultar API: Rate limit (429) após múltiplas tentativas."}

    except requests.exceptions.Timeout:
        logger.error(f"Timeout ao consultar QSA para CNPJ: {cnpj}")
        return {"error": "Erro de conexão: Timeout"}
    except requests.exceptions.RequestException as e:
        logger.error(f"Erro na requisição QSA para CNPJ {cnpj}: {str(e)}")
        return {"error": f"Erro de conexão: {str(e)}"}
    except Exception as e:
        logger.error(f"Erro inesperado ao consultar QSA para CNPJ {cnpj}: {str(e)}")
        return {"error": f"Erro inesperado no servidor: {str(e)}"}

# --- Verificações Assíncronas (Adaptado) ---
# No ambiente Flask/Render, usaremos workers (Gunicorn/Celery) ou background tasks se necessário.
# Para simplificar, vamos executar sequencialmente por enquanto, mas a estrutura está aqui.

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
        fb_content = extract_facebook_ads(instagram_username)
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
        google_content = extract_google_ads(domain)
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
            results["qsa_data"] = qsa_result # Mantém a mensagem de erro
            results["error_messages"].append(f"QSA: {qsa_result.get('error', 'Erro desconhecido')}")
        logger.info(f"Resultado QSA para {cnpj}: {results['qsa_status']}")

    return results

