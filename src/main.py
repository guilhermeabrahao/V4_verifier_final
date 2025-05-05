# -*- coding: utf-8 -*-
import sys
import os
# Ensure src directory is in path - DO NOT CHANGE
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from flask import Flask, request, jsonify, render_template
import logging

# Import verification functions
from src.verifications import (
    run_verification_tasks, 
    extract_facebook_ads, 
    extract_google_ads, 
    analyze_ads_with_ai,
    consultar_qsa
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder="templates", static_folder="static")

# --- Scoring Logic (Based on index (2).html) ---

# Define points for each criterion
CRITERIA_POINTS = {
    # 1. Faixa de Faturamento (Single choice, handled in JS/Frontend logic)
    "faturamento_ate_100k": -100,
    "faturamento_100_200k": -100,
    "faturamento_200_400k": 0,
    "faturamento_401k_1M": 30,
    "faturamento_1M_4M": 30,
    # 2. Produto de Interesse
    "interesse_assessoria": 30,
    "interesse_estruturacao": 10,
    "interesse_alavancagem": 0,
    # 3. Perfil do Contato
    "perfil_nome_completo": 30,
    "perfil_linkedin": 30,
    "perfil_cargo_estrategico": 30,
    "perfil_cargo_tatico": 20,
    "perfil_cargo_operacional": 0,
    # 4. Qualidade do Contato
    "contato_email_corp": 10,
    "contato_email_pessoal": 0,
    # 5. Estrutura Digital
    "digital_site_funcional": 30,
    "digital_site_fora_ar": -20,
    "digital_produto_sinergia": 20,
    # 6. Redes Sociais
    "social_insta_site": 5,
    "social_insta_google": 10,
    "social_insta_5k": 20,
    "social_sem_presenca": -20,
    # 7. Validação da Empresa
    "validacao_cnpj_localizado": 10, # Automatic check can contribute here
    "validacao_pessoa_qsa": 30,      # Automatic check can contribute here
    "validacao_nome_generico": -30,
    # 8. Urgência
    "urgencia_imediata": 20,
    "urgencia_3_meses": 10,
    "urgencia_nao_informada": 0,
    # 9. Investimento Atual (Partially automated)
    "investimento_google_meta": 30, # Automatic check can contribute here
    "investimento_google": 20,      # Automatic check can contribute here
    "investimento_meta": 20,        # Automatic check can contribute here
    # 10. Confirmações Manuais
    "manual_verificado_maps": 20,
    "manual_redirecionado_assessoria": 15
}

def calculate_score(checklist_data, verification_results):
    """Calculates the total score based on checklist and verification results."""
    total = 0
    logger.info(f"Calculating score with checklist: {checklist_data}")
    
    # Calculate score from checklist items
    for key, value in checklist_data.items():
        # Ensure value is truthy (e.g., checkbox checked, radio selected)
        if key in CRITERIA_POINTS and value: 
            # Handle radio button groups - Frontend should send only the selected one as true
            # No special handling needed here if frontend sends data correctly
            total += CRITERIA_POINTS.get(key, 0)

    logger.info(f"Score after checklist: {total}")

    # Add/Subtract points based on automatic verification results
    # CNPJ Localizado (if QSA found)
    if verification_results.get("qsa_status") == "found":
        total += CRITERIA_POINTS["validacao_cnpj_localizado"]
        # Pessoa no QSA (Check if QSA list is not empty)
        # Ensure qsa_data and qsa exist before checking length
        qsa_data = verification_results.get("qsa_data", {})
        if qsa_data and qsa_data.get("qsa") and len(qsa_data["qsa"]) > 0:
            total += CRITERIA_POINTS["validacao_pessoa_qsa"]
            
    # Investimento Atual (Google/Meta)
    google_active = verification_results.get("google_ads_status") == "active"
    fb_active = verification_results.get("facebook_ads_status") == "active"

    # Reset previous investment points if they were manually checked
    # (Assuming manual checkboxes for investment are removed/ignored now)
    # No need to reset if manual checkboxes are gone

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
    # else: stays as "descartar"

    qualification["teto"] = teto

    # Ensure valor_atual is treated as a number
    valor_atual_num = float(valor_atual) if valor_atual else 0
    if valor_atual_num > teto and score >= 80:
        qualification["alert"] = f"❗ Valor atual (R$ {valor_atual_num:.2f}) ultrapassou teto sugerido (R$ {teto:.2f}). Reavaliar risco!"

    logger.info(f"Qualification result: {qualification}")
    return qualification

# --- Flask Routes ---

@app.route("/")
def home():
    """Renders the main qualification page."""
    # Pass criteria points to the template if needed for display, or handle in JS
    return render_template("index.html") 

# --- Individual Verification Endpoints ---

@app.route("/api/verify/instagram", methods=["POST"])
def verify_instagram_ads_route():
    data = request.json
    username = data.get("instagram_username", "").strip()
    if not username:
        return jsonify({"error": "Instagram username is required"}), 400
    
    logger.info(f"Individual verification request for Instagram: {username}")
    fb_content = extract_facebook_ads(username)
    status = "error"
    message = "Erro na extração"
    if "Erro ao extrair" in fb_content:
        message = fb_content
    elif not fb_content:
        status = "inactive" # Or error? Let's assume inactive if empty after successful extraction attempt
        message = "Conteúdo não extraído ou vazio"
    else:
        try:
            has_fb_ads = analyze_ads_with_ai("facebook", fb_content, username)
            status = "active" if has_fb_ads else "inactive"
            message = "Ativo" if status == "active" else "Inativo"
        except Exception as e:
            logger.error(f"AI Analysis error for {username}: {e}")
            message = f"Erro na análise: {e}"

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
    status = "error"
    message = "Erro na extração"
    if "Erro ao extrair" in google_content:
        message = google_content
    elif not google_content:
        status = "inactive"
        message = "Conteúdo não extraído ou vazio"
    else:
        try:
            has_google_ads = analyze_ads_with_ai("google", google_content, domain)
            status = "active" if has_google_ads else "inactive"
            message = "Ativo" if status == "active" else "Inativo"
        except Exception as e:
            logger.error(f"AI Analysis error for {domain}: {e}")
            message = f"Erro na análise: {e}"
            
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
        # Simplify QSA data for direct display
        qsa_data_simplified = {
            "razao_social": qsa_result.get("razao_social", "N/A"),
            "situacao": qsa_result.get("situacao", "N/A"),
            "socios": [f"{s.get("nome", "?")} ({s.get("qual", "?")})" for s in qsa_result.get("qsa", [])]
        }
    elif "não encontrado" in message.lower() or "inválido" in message.lower():
        status = "not_found"
        message = "Não encontrado ou inválido"
    # else: status remains "error"

    logger.info(f"Individual verification result for QSA {cnpj}: {status}")
    return jsonify({"status": status, "message": message, "data": qsa_data_simplified})

# --- Main Qualification Endpoint (Modified) ---

@app.route("/api/qualify", methods=["POST"])
def qualify_lead():
    """Receives lead data, runs *all* verifications, calculates score, and returns qualification."""
    try:
        data = request.json
        if not data:
            return jsonify({"error": "Invalid JSON data"}), 400

        logger.info(f"Received full qualification request: {data}")

        # Extract data
        instagram_username = data.get("instagram_username", "").strip()
        domain = data.get("domain", "").strip()
        cnpj = data.get("cnpj", "").strip()
        valor_inicial = float(data.get("valorInicial", 0))
        valor_atual = float(data.get("valorAtual", 0))
        checklist_data = data.get("checklist", {})

        # Run *all* automatic verifications needed for scoring
        # Note: This runs them again, even if run individually before. 
        # Could be optimized by passing previous results, but this is simpler for now.
        verification_results = run_verification_tasks(instagram_username, domain, cnpj)
        logger.info(f"Full verification results for scoring: {verification_results}")

        # Calculate score
        score = calculate_score(checklist_data, verification_results)

        # Determine qualification
        qualification = determine_qualification(score, valor_inicial, valor_atual)

        # Combine results for the final response
        response_data = {
            "score": score,
            "qualification": qualification,
            "verifications": verification_results # Send back the detailed results
        }

        return jsonify(response_data), 200

    except ValueError as ve:
        logger.error(f"Value error in /api/qualify: {str(ve)}", exc_info=True)
        return jsonify({"error": f"Erro nos valores fornecidos: {str(ve)}"}), 400
    except Exception as e:
        logger.error(f"Error in /api/qualify: {str(e)}", exc_info=True)
        return jsonify({"error": "Internal server error occurred."}), 500

# --- Main Execution (for local testing, Render uses Gunicorn) ---
if __name__ == "__main__":
    # Make sure to set the PORT environment variable for Render
    port = int(os.environ.get("PORT", 5001)) # Use a different port if 5000 is busy
    # Run on 0.0.0.0 to be accessible externally
    app.run(host="0.0.0.0", port=port, debug=True) # Set debug=True for development

