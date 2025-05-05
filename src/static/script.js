// --- Helper Functions ---

function showLoading(elementId, message = "Verificando...") {
    const el = document.getElementById(elementId);
    if (el) {
        el.innerHTML = `<span class="loading-indicator"><i class="fas fa-spinner fa-spin"></i> ${message}</span>`;
        el.className = "verification-result loading"; // Reset classes and add loading
    }
}

function updateResult(elementId, status, message, data = null) {
    const el = document.getElementById(elementId);
    if (el) {
        let html = `<span class="status-${status}">${message}</span>`;
        // Special handling for QSA data
        if (elementId === "qsa_result" && status === "found" && data) {
            html += `<div class="qsa-details">`;
            html += `<strong>Razão Social:</strong> ${data.razao_social || "N/A"}<br>`;
            html += `<strong>Situação:</strong> ${data.situacao || "N/A"}<br>`;
            if (data.socios && data.socios.length > 0) {
                html += `<strong>Sócios:</strong> ${data.socios.join(", ")}`;
            }
            html += `</div>`;
        }
        el.innerHTML = html;
        el.className = `verification-result status-${status}`;
    }
}

function getStatusText(status) {
    // Used for the final qualification details
    switch (status) {
        case "active": return "Ativo";
        case "inactive": return "Inativo";
        case "found": return "Encontrado";
        case "not_found": return "Não encontrado";
        case "error": return "Erro";
        case "pending": return "Pendente";
        case "not_checked": return "Não verificado";
        default: return status;
    }
}

// --- Individual Verification Functions ---

async function verifyInstagram() {
    const username = document.getElementById("instagram_username").value.trim();
    const resultDivId = "instagram_result";
    if (!username) {
        updateResult(resultDivId, "error", "Nome de usuário do Instagram é obrigatório.");
        return;
    }
    showLoading(resultDivId);
    try {
        const response = await fetch("/api/verify/instagram", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ instagram_username: username }),
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || `HTTP error ${response.status}`);
        updateResult(resultDivId, data.status, data.message);
    } catch (error) {
        console.error("Error verifying Instagram:", error);
        updateResult(resultDivId, "error", `Erro: ${error.message}`);
    }
}

async function verifyGoogle() {
    const domain = document.getElementById("domain").value.trim();
    const resultDivId = "google_result";
    if (!domain) {
        updateResult(resultDivId, "error", "Domínio do website é obrigatório.");
        return;
    }
    showLoading(resultDivId);
    try {
        const response = await fetch("/api/verify/google", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ domain: domain }),
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || `HTTP error ${response.status}`);
        updateResult(resultDivId, data.status, data.message);
    } catch (error) {
        console.error("Error verifying Google:", error);
        updateResult(resultDivId, "error", `Erro: ${error.message}`);
    }
}

async function verifyQSA() {
    const cnpj = document.getElementById("cnpj").value.trim();
    const resultDivId = "qsa_result";
    if (!cnpj) {
        updateResult(resultDivId, "error", "CNPJ é obrigatório.");
        return;
    }
    showLoading(resultDivId);
    try {
        const response = await fetch("/api/verify/qsa", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ cnpj: cnpj }),
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || `HTTP error ${response.status}`);
        updateResult(resultDivId, data.status, data.message, data.data); // Pass simplified data
    } catch (error) {
        console.error("Error verifying QSA:", error);
        updateResult(resultDivId, "error", `Erro: ${error.message}`);
    }
}

// --- Main Qualification Function ---

async function qualifyLead() {
    const calculateButton = document.getElementById("calculateButton");
    const loadingDiv = document.getElementById("loading");
    const resultSection = document.getElementById("resultSection");
    const resultadoDiv = document.getElementById("resultado");
    const verificationDetailsDiv = document.getElementById("verificationDetails");
    const errorMessagesDiv = document.getElementById("errorMessages");

    // Disable button and show loading overlay
    calculateButton.disabled = true;
    loadingDiv.style.display = "flex"; // Use flex for centering
    resultSection.style.display = "none";
    resultadoDiv.innerHTML = "";
    verificationDetailsDiv.innerHTML = "";
    errorMessagesDiv.innerHTML = "";
    resultadoDiv.className = "result-box"; // Reset class

    // --- गैदर डेटा ---
    const instagram_username = document.getElementById("instagram_username").value.trim();
    const domain = document.getElementById("domain").value.trim();
    const cnpj = document.getElementById("cnpj").value.trim();
    const valorInicial = parseFloat(document.getElementById("valorInicial").value || 0);
    const valorAtual = parseFloat(document.getElementById("valorAtual").value || 0);

    // गैदर चेकलिस्ट डेटा
    const checklistData = {};
    const checkboxes = document.querySelectorAll("#leadForm input[type=checkbox]");
    checkboxes.forEach(cb => {
        checklistData[cb.id] = cb.checked;
    });

    // गैदर रेडियो बटन डेटा
    const radioGroups = ["faturamento", "interesse", "cargo", "email", "urgencia"];
    radioGroups.forEach(groupName => {
        const selectedRadio = document.querySelector(`input[name="${groupName}"]:checked`);
        if (selectedRadio) {
            checklistData[selectedRadio.value] = true; // Key is the value attribute of the radio
        }
    });

    // Validate required fields for final calculation
    if (valorInicial <= 0 || valorAtual < 0) {
        alert("Por favor, preencha os valores inicial e atual do leilão para calcular a pontuação final.");
        loadingDiv.style.display = "none";
        calculateButton.disabled = false;
        return;
    }
    // No need to validate insta/domain/cnpj here, as scoring handles missing ones

    const payload = {
        instagram_username: instagram_username,
        domain: domain,
        cnpj: cnpj,
        valorInicial: valorInicial,
        valorAtual: valorAtual,
        checklist: checklistData
    };

    // --- एपीआई कॉल (Main Qualification) ---
    try {
        const response = await fetch("/api/qualify", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });

        const data = await response.json();
        resultSection.style.display = "block"; // Show results section

        if (!response.ok) {
            throw new Error(data.error || `HTTP error! status: ${response.status}`);
        }

        // --- डिस्प्ले परिणाम ---
        // स्कोर और क्वालिफिकेशन
        resultadoDiv.innerHTML = `Pontuação Final: <strong>${data.score}</strong><br>`;
        resultadoDiv.innerHTML += data.qualification.message;
        resultadoDiv.className = `result-box status-${data.qualification.status}`;
        if (data.qualification.alert) {
            resultadoDiv.innerHTML += `<div class="alert">${data.qualification.alert}</div>`;
        }

        // वेरिफिकेशन डिटेल्स (from the final calculation)
        let detailsHTML = "<ul>";
        detailsHTML += `<li class="status-${data.verifications.facebook_ads_status}">Anúncios Instagram/Meta: ${getStatusText(data.verifications.facebook_ads_status)}</li>`;
        detailsHTML += `<li class="status-${data.verifications.google_ads_status}">Anúncios Google: ${getStatusText(data.verifications.google_ads_status)}</li>`;
        detailsHTML += `<li class="status-${data.verifications.qsa_status}">Consulta QSA: ${getStatusText(data.verifications.qsa_status)}</li>`;
        // Add QSA details if found
        if (data.verifications.qsa_status === "found" && data.verifications.qsa_data) {
             detailsHTML += `<li class="qsa-summary"> (Razão: ${data.verifications.qsa_data.razao_social || "N/A"}, Situação: ${data.verifications.qsa_data.situacao || "N/A"})</li>`;
        }
        detailsHTML += "</ul>";
        verificationDetailsDiv.innerHTML = detailsHTML;

        // एरर संदेश (from the final calculation)
        if (data.verifications.error_messages && data.verifications.error_messages.length > 0) {
            let errorHTML = "<ul>";
            data.verifications.error_messages.forEach(msg => {
                errorHTML += `<li class="status-error">${msg}</li>`;
            });
            errorHTML += "</ul>";
            errorMessagesDiv.innerHTML = errorHTML;
            errorMessagesDiv.style.display = "block";
        } else {
             errorMessagesDiv.innerHTML = "";
             errorMessagesDiv.style.display = "none";
        }

    } catch (error) {
        console.error("Error qualifying lead:", error);
        resultadoDiv.innerHTML = `<p class="status-error">Erro ao calcular pontuação final: ${error.message}</p>`;
        resultadoDiv.className = "result-box status-error";
        resultSection.style.display = "block"; // Show section even on error
        errorMessagesDiv.innerHTML = ""; // Clear specific error messages div
        errorMessagesDiv.style.display = "none";
    } finally {
        // Re-enable button and hide loading overlay
        loadingDiv.style.display = "none";
        calculateButton.disabled = false;
    }
}

// --- Event Listeners ---

// Add event listener to CNPJ field for basic formatting
document.getElementById("cnpj").addEventListener("input", function (e) {
    let value = e.target.value.replace(/\D/g, ""); // Remove non-digits
    value = value.substring(0, 14); // Limit to 14 digits
    if (value.length > 12) {
        value = value.replace(/^(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})$/, "$1.$2.$3/$4-$5");
    } else if (value.length > 8) {
        value = value.replace(/^(\d{2})(\d{3})(\d{3})(\d{0,4})$/, "$1.$2.$3/$4");
    } else if (value.length > 5) {
        value = value.replace(/^(\d{2})(\d{3})(\d{0,3})$/, "$1.$2.$3");
    } else if (value.length > 2) {
        value = value.replace(/^(\d{2})(\d{0,3})$/, "$1.$2");
    }
    e.target.value = value;
});

// Optional: Clear individual results when input changes?
// document.getElementById("instagram_username").addEventListener("input", () => document.getElementById("instagram_result").innerHTML = "");
// document.getElementById("domain").addEventListener("input", () => document.getElementById("google_result").innerHTML = "");
// document.getElementById("cnpj").addEventListener("input", () => document.getElementById("qsa_result").innerHTML = "");

