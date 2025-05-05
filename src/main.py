
import sys
import os
# Ensure src directory is in path - DO NOT CHANGE
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from flask import Flask, request, jsonify, render_template
import logging

# Import verification functions (Corrected Imports for v5)
# O patch já deve ter sido executado antes desta linha
from src.verifications import (
    run_verification_tasks, 
    extract_facebook_ads, 
    extract_google_ads, 
    analyze_ads_with_ai,      # Use the generic AI function
    consultar_qsa
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder="templates", static_folder="static")

# --- Scoring Logic (No changes needed) ---

# Define points for each criterion
CRITERIA_POINTS = {
    # ... (points remain the same)
    "faturamento_ate_100k": -100,
    "faturamento_100_200k": -100,
    "faturamento_200_400k": 0,
    "faturamento_401k_1M": 30,
    "faturamento_1M_4M": 30,
    "interesse_assessoria": 30,
    "interesse_estruturacao": 10,
    "interesse_alavancagem": 0,
    "perfil_nome_completo": 30,
    "perfil_linkedin": 30,
    "perfil_cargo_estrategico": 30,
    "perfil_cargo_tatico": 20,
    "perfil_cargo_operacional": 0,
    "contato_email_corp": 10,
    "contato_email_pessoal": 0,
    "digital_site_funcional": 30,
    "digital_site_fora_ar": -20,
    "digital_produto_sinergia": 20,
    "social_insta_site": 5,
    "social_insta_google": 10,
    "social_insta_5k": 20,
    "social_sem_presenca": -20,
    "validacao_cnpj_localizado": 10,
    "validacao_pessoa_qsa": 30,
    "validacao_nome_generico": -30,
    "urgencia_imediata": 20,
    "urgencia_3_meses": 10,
    "urgencia_nao_informada": 0,
    "investimento_google_meta": 30,
    "investimento_google": 20,
    "investimento_meta": 20,
    "manual_verificado_maps": 20,
    "manual_redirecionado_assessoria": 15
}

def calculate_score(checklist_data, verification_results):
    """Calculates the total score based on checklist and verification results."""
    total = 0
    logger.info(f"Calculating score with checklist: {checklist_data}")
    
    for key, value in checklist_data.items():
        if key in CRITERIA_POINTS and value: 
            total += CRITERIA_POINTS.get(key, 0)

    logger.info(f"Score after checklist: {total}")

    if verification_results.get("qsa_status") == "found":
        total += CRITERIA_POINTS["validacao_cnpj_localizado"]
        qsa_data = verification_results.get("qsa_data", {})
        if qsa_data and qsa_data.get("qsa") and len(qsa_data["qsa"]) > 0:
            total += CRITERIA_POINTS["validacao_pessoa_qsa"]
            
    google_active = verification_results.get("google_ads_status") == "active"
    fb_active = verification_results.get("facebook_ads_status") == "active"

    if google_active and fb_active:
        total += CRITERIA_POINTS["investimento_google_meta"]
    elif google_active:
        total += CRITERIA_POINTS["investimento_google"]
    elif fb_active:
        total += CRITERIA_POINTS["investimento_meta"]
        
    logger.info(f"Final score after verifications: {total}")
    return total

def determine_qualification(score, valor_inicial, valor_atual):
    """Determines the lead qualification based on score and auction values."""
    qualification = {
        "status": "descartar",
        "message": "🔴 Descartar Lead",
        "teto": 0,
        "show_teto": False,
        "alert": None
    }
    teto = 0

    if score >= 130:
        teto = valor_inicial * 1.8
        qualification["status"] = "comprar"
        qualification["message"] = f"🟢 COMPRE JÁ liberado (Teto Sugerido: R$ {teto:.2f})"
        qualification["show_teto"] = True
    elif score >= 100:
        teto = valor_inicial * 1.3
        qualification["status"] = "acompanhar_alto"
        qualification["message"] = f"🟡 Acompanhar (Teto Sugerido: R$ {teto:.2f})"
        qualification["show_teto"] = True
    elif score >= 80:
        teto = valor_inicial
        qualification["status"] = "acompanhar_baixo"
        qualification["message"] = f"⚠️ Acompanhar (Teto Sugerido: R$ {teto:.2f})"
        qualification["show_teto"] = True

    qualification["teto"] = teto

    valor_atual_num = float(valor_atual) if valor_atual else 0
    if valor_atual_num > teto and score >= 80:
        qualification["alert"] = f"❗ Valor atual (R$ {valor_atual_num:.2f}) ultrapassou teto sugerido (R$ {teto:.2f}). Reavaliar risco!"

    logger.info(f"Qualification result: {qualification}")
    return qualification

# --- Flask Routes ---

@app.route("/")
def home():
    """Renders the main qualification page."""
    return render_template("index.html") 

# --- Individual Verification Endpoints (Corrected for v5) ---

@app.route("/api/verify/instagram", methods=["POST"])
def verify_instagram_ads_route():
    data = request.json
    username = data.get("instagram_username", "").strip()
    if not username:
        return jsonify({"error": "Instagram username is required"}), 400
    
    logger.info(f"Individual verification request for Instagram: {username}")
    fb_content = extract_facebook_ads(username)
    
    # Use the generic AI function for Facebook
    ai_status = analyze_ads_with_ai("facebook", fb_content, username)
    
    # Determine final status and message based on AI result
    status = "error"
    message = "Erro na verificação"
    
    if ai_status == "active":
        status = "active"
        message = "Ativo"
    elif ai_status == "inactive":
        status = "inactive"
        message = "Inativo"
    elif ai_status == "error_content":
        message = fb_content if "Erro ao extrair" in fb_content else "Conteúdo inválido ou vazio para análise."
    elif ai_status == "error_ai_key":
        message = "Erro: Chave da API OpenAI não configurada."
    elif ai_status == "error_ai_response":
        message = "Erro: Resposta inesperada da análise de IA."
    elif ai_status == "error_ai_exception":
        message = "Erro: Falha durante a execução da análise de IA."
    # Default to error if status is unexpected

    logger.info(f"Individual verification result for Instagram {username}: {status}")
    return jsonify({"status": status, "message": message})

@app.route("/api/verify/google", methods=["POST"])
def verify_google_ads_route():
    data = request.json
    domain = data.get("domain", "").strip()
    if not domain:
        return jsonify({"error": "Domain is required"}), 400

    logger.info(f"Individual verification request for Google: {domain}")
    google_content = extract_google_ads(domain)
    
    # Use the generic AI function for Google
    ai_status = analyze_ads_with_ai("google", google_content, domain)
    
    # Determine final status and message based on AI result
    status = "error"
    message = "Erro na verificação"
    
    if ai_status == "active":
        status = "active"
        message = "Ativo"
    elif ai_status == "inactive":
        status = "inactive"
        message = "Inativo"
    elif ai_status == "error_content":
        message = google_content if "Erro ao extrair" in google_content else "Conteúdo inválido ou vazio para análise."
    elif ai_status == "error_ai_key":
        message = "Erro: Chave da API OpenAI não configurada."
    elif ai_status == "error_ai_response":
        message = "Erro: Resposta inesperada da análise de IA."
    elif ai_status == "error_ai_exception":
        message = "Erro: Falha durante a execução da análise de IA."
    # Default to error if status is unexpected

    logger.info(f"Individual verification result for Google {domain}: {status}")
    return jsonify({"status": status, "message": message})

@app.route("/api/verify/qsa", methods=["POST"])
def verify_qsa_route():
    data = request.json
    cnpj = data.get("cnpj", "").strip()
    if not cnpj:
        return jsonify({"error": "CNPJ is required"}), 400

    logger.info(f"Individual verification request for QSA: {cnpj}")
    qsa_result = consultar_qsa(cnpj)
    status = "error"
    message = qsa_result.get("error", "Erro desconhecido")
    qsa_data_simplified = None

    if qsa_result.get("success"):
        status = "found"
        message = "Encontrado"
        qsa_data_simplified = {
            "razao_social": qsa_result.get("razao_social", "N/A"),
            "situacao": qsa_result.get("situacao", "N/A"),
            # Corrigido: Usar aspas simples dentro da f-string
            "socios": [f"{s.get('nome', '?')} ({s.get('qual', '?')})" for s in qsa_result.get("qsa", [])]
        }
    elif "inválido" in message.lower() or "não encontrado" in message.lower():
        status = "not_found"
        message = "Não encontrado ou inválido"

    logger.info(f"Individual verification result for QSA {cnpj}: {status}")
    return jsonify({"status": status, "message": message, "data": qsa_data_simplified})

# --- Main Qualification Endpoint (No changes needed here, uses run_verification_tasks) ---

@app.route("/api/qualify", methods=["POST"])
def qualify_lead():
    """Receives lead data, runs *all* verifications, calculates score, and returns qualification."""
    try:
        data = request.json
        if not data:
            return jsonify({"error": "Invalid JSON data"}), 400

        logger.info(f"Received full qualification request: {data}")

        instagram_username = data.get("instagram_username", "").strip()
        domain = data.get("domain", "").strip()
        cnpj = data.get("cnpj", "").strip()
        valor_inicial = float(data.get("valorInicial", 0))
        valor_atual = float(data.get("valorAtual", 0))
        checklist_data = data.get("checklist", {})

        # run_verification_tasks internally uses the generic analyze_ads_with_ai
        verification_results = run_verification_tasks(instagram_username, domain, cnpj)
        logger.info(f"Full verification results for scoring: {verification_results}")

        score = calculate_score(checklist_data, verification_results)
        qualification = determine_qualification(score, valor_inicial, valor_atual)

        response_data = {
            "score": score,
            "qualification": qualification,
            "verifications": verification_results
        }

        return jsonify(response_data), 200

    except ValueError as ve:
        logger.error(f"Value error in /api/qualify: {str(ve)}", exc_info=True)
        return jsonify({"error": f"Erro nos valores fornecidos: {str(ve)}"}), 400
    except Exception as e:
        logger.error(f"Error in /api/qualify: {str(e)}", exc_info=True)
        return jsonify({"error": "Internal server error occurred."}), 500

# --- Main Execution ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port, debug=True)


