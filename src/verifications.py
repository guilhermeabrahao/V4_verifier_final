# -*- coding: utf-8 -*-
# Patch para forçar o uso do pysqlite3
try:
    __import__('pysqlite3')
    import sys
    sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
    print("INFO: Successfully patched sqlite3 with pysqlite3")
except ImportError:
    print("WARNING: pysqlite3 not found, using system default sqlite3.")
# --- Fim do Patch ---

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

# --- Funções de Extração (sem alterações) --- 

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
            page.goto(url, timeout=60000)
            page.wait_for_selector("div[role=\"main\"]", timeout=45000) 
            page.wait_for_timeout(5000)
            text = page.inner_text("body")
            browser.close()
            logger.info(f"Extração da Facebook Ads Library concluída para: {instagram_username}")
            return text
    except Exception as e:
        logger.error(f"Erro ao extrair anúncios do Facebook para {instagram_username}: {str(e)}")
        return f"Erro ao extrair: {str(e)}"

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
            page.goto(url, timeout=60000)
            page.wait_for_selector("input[type=\"search\"]", timeout=45000)
            page.wait_for_timeout(7000)
            text = page.inner_text("body")
            browser.close()
            logger.info(f"Extração do Google Ads Transparency concluída para: {domain}")
            return text
    except Exception as e:
        logger.error(f"Erro ao extrair anúncios do Google para {domain}: {str(e)}")
        return f"Erro ao extrair: {str(e)}"

# --- Função de Análise com IA (Reimplementada para ser Genérica) --- 

def analyze_ads_with_ai(platform, content, query):
    """Analisa o conteúdo extraído usando CrewAI para determinar se há anúncios ativos.
    
    Args:
        platform (str): "facebook" ou "google".
        content (str): Conteúdo da página extraído.
        query (str): O username (facebook) ou domain (google) pesquisado.
    """
    if not OPENAI_API_KEY:
         logger.error("Chave API OpenAI não configurada. Análise de IA abortada.")
         # Retorna um status de erro específico para IA
         return "error_ai_key" 
    if not content or "Erro ao extrair" in content:
        logger.warning(f"Conteúdo inválido ou erro na extração para {query} na plataforma {platform}. Análise de IA abortada.")
        # Retorna um status de erro específico para conteúdo
        return "error_content" 

    try:
        logger.info(f"Iniciando análise de IA para {query} na plataforma {platform}")
        agent = Agent(
            role="Analista de Anúncios",
            goal=f"Interpretar o conteúdo da página da central de anúncios da {platform} para verificar se há anúncios ativos para ",
            backstory="Um especialista em marketing digital que analisa textos de páginas de bibliotecas de anúncios.",
            tools=[],
            verbose=False
        )

        # Corrigido: Simplificado negative_indicators
        if platform == "facebook":
            platform_name = "Biblioteca de Anúncios do Facebook"
            query_type = "usuário"
            negative_indicators = "'nenhum anúncio encontrado', '0 resultados'"
        elif platform == "google":
            platform_name = "Central de Transparência de Anúncios do Google"
            query_type = "domínio"
            negative_indicators = "'Nenhum anúncio foi encontrado', 'não veiculou anúncios'"
        else:
            logger.error(f"Plataforma desconhecida para análise de IA: {platform}")
            return "error_platform"

        task_description = (
            f"Analise o seguinte conteúdo da {platform_name} e determine se existem anúncios ATIVOS para o {query_type}.\n"
            f"Conteúdo da página:\n--- INÍCIO ---\n{content[:15000]}\n--- FIM ---\n\n"
            f"Procure por indicadores como {negative_indicators}, ou a presença explícita de anúncios listados (cards, imagens, textos de anúncios). "
            f"Considere que a página pode conter muitos elementos não relacionados a anúncios. Foque em encontrar evidências concretas de anúncios ativos. "
            f"Responda APENAS com \'Sim\' se encontrar anúncios ativos, ou \'Não\' caso contrário. Não inclua explicações."
        )

        task = Task(
            description=task_description,
            expected_output="\'Sim\' ou \'Não\'.",
            agent=agent
        )

        crew = Crew(agents=[agent], tasks=[task], verbose=False)
        result = crew.kickoff()
        logger.info(f"Resultado da análise de IA para {query} ({platform}): {result}")
        
        resposta_normalizada = str(result).strip().lower()
        if resposta_normalizada == "sim":
            return "active"
        elif resposta_normalizada == "não":
            return "inactive"
        else:
            # Se a IA não responder Sim/Não, considerar erro
            logger.warning(f"Resposta inesperada da IA para {query} ({platform}): {result}")
            return "error_ai_response"

    except Exception as e:
        logger.error(f"Erro durante a análise de IA para {query} ({platform}): {str(e)}")
        return "error_ai_exception" # Erro genérico na execução da IA

# --- Função de Verificação QSA (sem alterações) --- 

def consultar_qsa(cnpj):
    """Consulta o QSA de um CNPJ na API da ReceitaWS."""
    if not cnpj:
        return {"error": "CNPJ não fornecido"}
    try:
        cnpj_limpo = "".join(filter(str.isdigit, cnpj))
        if len(cnpj_limpo) != 14:
             return {"error": "CNPJ inválido"}
             
        url = f"https://www.receitaws.com.br/v1/cnpj/{cnpj_limpo}"
        logger.info(f"Consultando QSA para CNPJ: {cnpj_limpo}")
        
        max_retries = 3
        delay = 60
        for attempt in range(max_retries):
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
                # Tentar extrair mensagem de erro da API se disponível
                error_msg = f"Erro ao consultar API: {response.status_code}"
                try: 
                    error_data = response.json()
                    # Corrigido: Usar aspas simples para a chave do dicionário dentro da f-string
                    if error_data and 'message' in error_data:
                        error_msg += f" - {error_data['message']}"
                except: pass # Ignora se não for JSON
                return {"error": error_msg}
        
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

# --- Função Principal de Verificação (run_verification_tasks - Atualizada) --- 

def run_verification_tasks(instagram_username, domain, cnpj):
    """Executa todas as tarefas de verificação necessárias para a pontuação final."""
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

    # --- Verificação Facebook Ads (Usa IA) ---
    if instagram_username:
        logger.info(f"Iniciando verificação Facebook Ads para: {instagram_username}")
        fb_content = extract_facebook_ads(instagram_username)
        # Chama a função genérica de IA
        fb_status = analyze_ads_with_ai("facebook", fb_content, instagram_username)
        results["facebook_ads_status"] = fb_status # Status pode ser active, inactive, ou um erro específico
        if "error" in fb_status:
             error_detail = fb_content if fb_status == "error_content" else f"Erro na análise IA ({fb_status})"
             results["error_messages"].append(f"Facebook Ads: {error_detail}")
             results["facebook_ads_status"] = "error" # Simplifica para "error" no resultado final
        # Corrigido: Usar aspas simples para f-string ou variável intermediária
        fb_status_log = results["facebook_ads_status"]
        logger.info(f'Resultado Facebook Ads para {instagram_username}: {fb_status_log}')

    # --- Verificação Google Ads (Usa IA) ---
    if domain:
        logger.info(f"Iniciando verificação Google Ads para: {domain}")
        google_content = extract_google_ads(domain)
        # Chama a função genérica de IA
        google_status = analyze_ads_with_ai("google", google_content, domain)
        results["google_ads_status"] = google_status # Status pode ser active, inactive, ou um erro específico
        if "error" in google_status:
             error_detail = google_content if google_status == "error_content" else f"Erro na análise IA ({google_status})"
             results["error_messages"].append(f"Google Ads: {error_detail}")
             results["google_ads_status"] = "error" # Simplifica para "error" no resultado final
        # Corrigido: Usar aspas simples para f-string ou variável intermediária
        google_status_log = results["google_ads_status"]
        logger.info(f'Resultado Google Ads para {domain}: {google_status_log}')

    # --- Verificação QSA (sem alterações) ---
    if cnpj:
        logger.info(f"Iniciando verificação QSA para: {cnpj}")
        qsa_result = consultar_qsa(cnpj)
        if qsa_result.get("success"):
            results["qsa_status"] = "found"
            results["qsa_data"] = qsa_result
        else:
            # Verifica se o erro é "CNPJ inválido" ou "não encontrado" para status específico
            error_msg = qsa_result.get("error", "Erro desconhecido")
            if "inválido" in error_msg.lower() or "não encontrado" in error_msg.lower():
                 results["qsa_status"] = "not_found"
            else:
                 results["qsa_status"] = "error"
            results["qsa_data"] = qsa_result # Mantém a mensagem de erro
            results["error_messages"].append(f"QSA: {error_msg}")
        # Corrigido: Usar aspas simples para f-string ou variável intermediária
        qsa_status_log = results["qsa_status"]
        logger.info(f'Resultado QSA para {cnpj}: {qsa_status_log}')

    return results


