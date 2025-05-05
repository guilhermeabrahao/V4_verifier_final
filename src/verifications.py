# -*- coding: utf-8 -*-
import os
import time
import threading

# Add Selenium imports
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
# Consider webdriver_manager if chromedriver is not installed globally
# from webdriver_manager.chrome import ChromeDriverManager # Needs installation

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

# --- Funções de Extração (Modificadas para Selenium) ---

def setup_selenium_driver():
    """Configura e retorna uma instância do WebDriver do Selenium."""
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")  # Executar em modo headless
    options.add_argument("--no-sandbox") # Necessário para rodar como root/em container
    options.add_argument("--disable-dev-shm-usage") # Supera limitações de recursos
    options.add_argument("--disable-gpu") # Desabilitar GPU (geralmente recomendado em headless)
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36") # User agent comum
    options.add_argument("--window-size=1920,1080") # Definir tamanho da janela pode ajudar

    # Tenta usar chromedriver no PATH
    try:
        # Assume que chromedriver está no PATH
        # Se precisar instalar: sudo apt-get update && sudo apt-get install -y chromium-chromedriver
        service = ChromeService() 
        driver = webdriver.Chrome(service=service, options=options)
        logger.info("WebDriver do Selenium inicializado com sucesso.")
        return driver
    except Exception as e:
        logger.error(f"Erro ao configurar o WebDriver do Selenium: {e}. Verifique se o chromedriver está instalado e no PATH.")
        raise RuntimeError(f"Falha ao inicializar o Selenium WebDriver: {e}")


def extract_facebook_ads(instagram_username):
    """Extrai o conteúdo da Biblioteca de Anúncios do Facebook para um dado usuário do Instagram usando Selenium."""
    if not instagram_username:
        return ""
    driver = None # Inicializa driver como None
    try:
        url = f"https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=BR&q={instagram_username}&search_type=keyword"
        logger.info(f"Acessando Facebook Ads Library para: {instagram_username} com Selenium")

        driver = setup_selenium_driver()
        driver.get(url)

        # Esperar por um elemento que indique o carregamento dos resultados ou a ausência deles.
        wait = WebDriverWait(driver, 30) # Timeout de 30 segundos
        wait.until(
            EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Resultados') or contains(text(), 'Nenhum anúncio encontrado') or contains(@data-testid, 'pagination-controls') or contains(text(), 'Nenhum anúncio ativo')] | //*[@role='dialog']"))
            # Adicionado @role='dialog' para capturar possíveis pop-ups/modais de consentimento que podem bloquear a interação
        )
        
        # Verifica se há algum diálogo/modal (ex: cookies) e tenta fechar se necessário
        try:
            close_button = driver.find_element(By.XPATH, "//div[@aria-label='Fechar' or @aria-label='Close' or contains(@aria-label, 'cookie')]//div[@role='button']")
            if close_button.is_displayed():
                logger.info("Fechando diálogo de consentimento/cookies.")
                close_button.click()
                time.sleep(1) # Pequena pausa após fechar
        except Exception:
            pass # Ignora se o botão de fechar não for encontrado

        # Espera adicional curta para permitir carregamento dinâmico final
        time.sleep(3)

        # Extrair o texto do corpo da página
        text = driver.find_element(By.TAG_NAME, 'body').text
        logger.info(f"Extração da Facebook Ads Library concluída para: {instagram_username}")
        return text

    except TimeoutException:
        logger.error(f"Timeout ao esperar pelo conteúdo da Facebook Ads Library para {instagram_username}")
        try:
            if driver:
                 text = driver.find_element(By.TAG_NAME, 'body').text
                 if text:
                     logger.warning(f"Conteúdo parcial extraído após timeout para {instagram_username}")
                     return text
        except Exception as inner_e:
             logger.error(f"Erro ao tentar extrair conteúdo parcial após timeout para {instagram_username}: {inner_e}")
        return f"Erro ao extrair: Timeout esperando pelo conteúdo principal."
    except WebDriverException as e:
         logger.error(f"Erro do WebDriver ao extrair anúncios do Facebook para {instagram_username}: {str(e)}")
         return f"Erro ao extrair: Erro do WebDriver ({type(e).__name__})."
    except Exception as e:
        logger.error(f"Erro inesperado ao extrair anúncios do Facebook para {instagram_username}: {str(e)}")
        return f"Erro ao extrair: {str(e)}"
    finally:
        if driver:
            driver.quit() # Garante que o navegador feche

def extract_google_ads(domain):
    """Extrai o conteúdo do Centro de Transparência de Anúncios do Google para um dado domínio usando Selenium."""
    if not domain:
        return ""
    driver = None # Inicializa driver como None
    try:
        url = f"https://adstransparency.google.com/?region=BR&domain={domain}"
        logger.info(f"Acessando Google Ads Transparency para: {domain} com Selenium")

        driver = setup_selenium_driver()
        driver.get(url)

        # Esperar por um elemento que indique o carregamento.
        wait = WebDriverWait(driver, 30) # Timeout de 30 segundos
        wait.until(
            EC.presence_of_element_located((By.XPATH, "//*[contains(translate(text(), 'ANÚNCIOS', 'anúncios'), 'anúncio') or contains(text(), 'Privacidade') or contains(text(), 'Termos') or contains(text(), 'Nenhum anúncio encontrado')] | //footer"))
            # Espera por 'anúncio', 'Nenhum anúncio', 'Privacidade', 'Termos' ou o elemento footer
        )

        # Espera adicional curta
        time.sleep(3)

        # Extrair o texto do corpo da página
        text = driver.find_element(By.TAG_NAME, 'body').text
        logger.info(f"Extração do Google Ads Transparency concluída para: {domain}")
        return text

    except TimeoutException:
        logger.error(f"Timeout ao esperar pelo conteúdo do Google Ads Transparency para {domain}")
        try:
            if driver:
                 text = driver.find_element(By.TAG_NAME, 'body').text
                 if text:
                     logger.warning(f"Conteúdo parcial extraído após timeout para {domain}")
                     return text
        except Exception as inner_e:
             logger.error(f"Erro ao tentar extrair conteúdo parcial após timeout para {domain}: {inner_e}")
        return f"Erro ao extrair: Timeout esperando pelo conteúdo principal."
    except WebDriverException as e:
         logger.error(f"Erro do WebDriver ao extrair anúncios do Google para {domain}: {str(e)}")
         return f"Erro ao extrair: Erro do WebDriver ({type(e).__name__})."
    except Exception as e:
        logger.error(f"Erro inesperado ao extrair anúncios do Google para {domain}: {str(e)}")
        return f"Erro ao extrair: {str(e)}"
    finally:
        if driver:
            driver.quit() # Garante que o navegador feche


# --- Função de Análise com IA (Mantida como original) ---

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

        # Limita o tamanho do conteúdo passado para a IA para evitar estouro de token/custo
        max_content_length = 15000
        conteudo_limitado = conteudo[:max_content_length]

        if plataforma == "facebook":
            task_description = (
                f"Analise o seguinte conteúdo da Biblioteca de Anúncios do Facebook e determine se existem anúncios ATIVOS para o usuário '{consulta}'.\n"
                f"Conteúdo da página:\n--- INÍCIO ---\n{conteudo_limitado}\n--- FIM ---\n\n"
                f"Procure por indicadores como 'nenhum anúncio encontrado', '0 resultados', ou a presença explícita de anúncios listados. "
                f"Responda APENAS com 'Sim' se encontrar anúncios ativos, ou 'Não' caso contrário. Não inclua explicações."
            )
        else: # google
            task_description = (
                f"Analise o seguinte conteúdo do Centro de Transparência de Anúncios do Google e determine se existem anúncios ATIVOS para o domínio '{consulta}'.\n"
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
        # Normaliza a resposta para garantir que seja 'sim' ou 'nao'
        resposta_normalizada = str(result).strip().lower()
        return resposta_normalizada == "sim"

    except Exception as e:
        logger.error(f"Erro durante a análise de IA para {consulta} ({plataforma}): {str(e)}")
        return False # Retorna False em caso de erro na IA

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

        # Tentar até 3 vezes com espera exponencial em caso de rate limit (429)
        max_retries = 3
        delay = 60 # segundos
        for attempt in range(max_retries):
            try:
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
            except requests.exceptions.Timeout:
                 logger.error(f"Timeout na tentativa {attempt + 1} ao consultar QSA para CNPJ: {cnpj}")
                 if attempt < max_retries - 1:
                     time.sleep(5) # Pequena pausa antes de tentar novamente após timeout
                 else:
                     return {"error": "Erro de conexão: Timeout persistente"}
            except requests.exceptions.RequestException as e:
                 logger.error(f"Erro na requisição QSA (tentativa {attempt + 1}) para CNPJ {cnpj}: {str(e)}")
                 if attempt < max_retries - 1:
                     time.sleep(5) # Pequena pausa antes de tentar novamente
                 else:
                    return {"error": f"Erro de conexão: {str(e)}"}

        # Caso esgote as tentativas
        return {"error": "Erro ao consultar API após múltiplas tentativas."}

    except Exception as e:
        logger.error(f"Erro inesperado ao consultar QSA para CNPJ {cnpj}: {str(e)}")
        return {"error": f"Erro inesperado no servidor: {str(e)}"}


# --- Verificações (Mantida como original, mas agora usa as funções Selenium) ---
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
        fb_content = extract_facebook_ads(instagram_username) # Agora usa Selenium
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
        google_content = extract_google_ads(domain) # Agora usa Selenium
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

# --- Bloco Principal (Exemplo de uso, se necessário para teste) ---
# if __name__ == '__main__':
#     # Exemplo de como chamar (requer .env com OPENAI_API_KEY)
#     test_insta = "usuario_teste_instagram" # Substituir por um usuário real para teste
#     test_domain = "exemplodominio.com.br" # Substituir por um domínio real para teste
#     test_cnpj = "00000000000191" # Substituir por um CNPJ real para teste
#
#     # Instalar dependências antes: pip install selenium python-dotenv crewai requests
#     # Pode ser necessário instalar chromedriver: sudo apt-get update && sudo apt-get install -y chromium-chromedriver
#
#     print(f"Iniciando verificações para Instagram: {test_insta}, Domínio: {test_domain}, CNPJ: {test_cnpj}")
#     resultados = run_verification_tasks(test_insta, test_domain, test_cnpj)
#     print("\n--- Resultados Finais ---")
#     import json
#     print(json.dumps(resultados, indent=2, ensure_ascii=False))
#     print("------------------------")

