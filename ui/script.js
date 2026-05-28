let backend;

const output = document.getElementById("password-output");
const strengthBar = document.getElementById("strength-bar");
const entropyVal = document.getElementById("entropy-val");
const bruteVal = document.getElementById("brute-val");
const lengthSlider = document.getElementById("length-slider");
const lengthLabel = document.getElementById("length-val");
const lengthLabelStat = document.getElementById("length-label");
const breachStatus = document.getElementById("breach-status");
const historyList = document.getElementById("history-list");

if (typeof QWebChannel === "undefined" || typeof qt === "undefined") {
    output.innerText = "Backend unavailable";
} else {
    new QWebChannel(qt.webChannelTransport, function (channel) {
        backend = channel.objects.backend;
        loadHistory();
    });
}

function callBackend(methodName, ...args) {
    return new Promise((resolve, reject) => {
        if (!backend || typeof backend[methodName] !== "function") {
            reject(new Error(`Backend method not available: ${methodName}`));
            return;
        }

        try {
            backend[methodName](...args, resolve);
        } catch (error) {
            reject(error);
        }
    });
}

lengthSlider.oninput = () => {
    lengthLabel.innerText = lengthSlider.value;
    lengthLabelStat.innerText = lengthSlider.value;
};

async function generate() {
    if (!backend) return;

    const config = {
        length: parseInt(lengthSlider.value, 10),
        include_upper: document.getElementById("upper").checked,
        include_lower: document.getElementById("lower").checked,
        include_digits: document.getElementById("digits").checked,
        include_symbols: document.getElementById("symbols").checked,
        include_unicode: false
    };

    const resRaw = await callBackend(
        "generate_password",
        config.length,
        config.include_upper,
        config.include_lower,
        config.include_digits,
        config.include_symbols,
        config.include_unicode
    );
    const res = JSON.parse(resRaw);

    updateUI(res);
    await callBackend("save_to_history", "Standard", config.length, res.entropy);
    loadHistory();
}

async function generateDiceware() {
    if (!backend) return;

    const resRaw = await callBackend("generate_diceware", 8);
    const res = JSON.parse(resRaw);
    updateUI(res);
    await callBackend("save_to_history", "Diceware", res.password.length, res.entropy);
    loadHistory();
}

async function generateBatch() {
    if (!backend) return;

    const len = parseInt(lengthSlider.value, 10);
    const resultsRaw = await callBackend("generate_batch", 100, len);
    const results = JSON.parse(resultsRaw);

    output.innerText = results.map((r) => r.password).join("\n");
    output.style.fontSize = "0.8rem";
    output.style.whiteSpace = "pre-wrap";
    output.style.overflowY = "auto";
    output.style.maxHeight = "200px";

    entropyVal.innerText = "~" + Math.round(results[0].entropy) + " bits";
    bruteVal.innerText = "N/A (Batch)";
    await callBackend("save_to_history", "Batch (100)", len, results[0].entropy);
    loadHistory();
}

function updateUI(res) {
    output.style.fontSize = "1.5rem";
    output.style.whiteSpace = "normal";
    output.style.overflowY = "visible";
    output.style.maxHeight = "none";
    output.innerText = res.password;
    entropyVal.innerText = Math.round(res.entropy) + " bits";
    bruteVal.innerText = res.brute_force;

    const strength = Math.min((res.entropy / 200) * 100, 100);
    strengthBar.style.width = strength + "%";

    if (strength < 40) {
        strengthBar.style.backgroundColor = "var(--danger)";
    } else if (strength < 70) {
        strengthBar.style.backgroundColor = "var(--warning)";
    } else {
        strengthBar.style.backgroundColor = "var(--success)";
    }

    breachStatus.style.display = "none";
}

async function checkBreach() {
    const pwd = output.innerText;
    if (pwd === "Click Generate" || pwd.includes("\n") || !backend) return;

    breachStatus.style.display = "block";
    breachStatus.innerText = "Checking API...";
    breachStatus.style.color = "var(--text-dim)";

    const resRaw = await callBackend("check_pwned", pwd);
    const res = JSON.parse(resRaw);

    if (res.status === "pwned") {
        breachStatus.innerText = `Warning: BREACHED! This password appeared in ${res.count} data breaches.`;
        breachStatus.style.color = "var(--danger)";
    } else if (res.status === "clean") {
        breachStatus.innerText = "Secure! No breach detected.";
        breachStatus.style.color = "var(--success)";
    } else {
        breachStatus.innerText = "Error connecting to security API.";
        breachStatus.style.color = "var(--danger)";
    }
}

async function loadHistory() {
    if (!backend) return;

    const historyRaw = await callBackend("get_history");
    const history = JSON.parse(historyRaw);
    historyList.innerHTML = history.map((item) => `
        <div class="history-item">
            <span>[${item.time}] ${item.label}</span>
            <span>${item.len} chars / ${Math.round(item.entropy)} bits</span>
        </div>
    `).join("");
}

async function clearHistory() {
    if (confirm("Delete all history?") && backend) {
        await callBackend("clear_history");
        loadHistory();
    }
}

async function copyToClipboard(button) {
    const text = output.innerText;
    if (text === "Click Generate" || !button) return;

    try {
        if (navigator.clipboard && window.isSecureContext) {
            await navigator.clipboard.writeText(text);
        } else {
            fallbackCopy(text);
        }
        button.innerText = "Copied!";
    } catch (error) {
        button.innerText = "Copy failed";
    }

    setTimeout(() => {
        button.innerText = "Copy";
    }, 2000);
}

function fallbackCopy(text) {
    const textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.setAttribute("readonly", "");
    textarea.style.position = "fixed";
    textarea.style.opacity = "0";
    document.body.appendChild(textarea);
    textarea.select();
    document.execCommand("copy");
    document.body.removeChild(textarea);
}
