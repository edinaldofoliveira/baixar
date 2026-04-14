const urlInput = document.getElementById('url-input');
const fetchBtn = document.getElementById('fetch-btn');
const btnText = document.getElementById('btn-text');
const btnLoader = document.getElementById('btn-loader');
const resultContainer = document.getElementById('result-container');
const formatList = document.getElementById('format-list');
const downloadArea = document.getElementById('download-area');
const selectionArea = document.getElementById('selection-area');
const progressBar = document.getElementById('progress-bar');
const statusText = document.getElementById('status-text');
const speedText = document.getElementById('speed-text');
const etaText = document.getElementById('eta-text');
const finishBtnContainer = document.getElementById('finish-btn-container');
const downloadLink = document.getElementById('download-link');

let currentJobId = null;

fetchBtn.addEventListener('click', async () => {
    const url = urlInput.value.trim();
    if (!url) return alert('Por favor, insira uma URL');

    setLoading(true);
    try {
        const response = await fetch('/info', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url })
        });
        
        const data = await response.json();
        if (data.error) throw new Error(data.error);

        displayInfo(data);
    } catch (err) {
        alert('Erro: ' + err.message);
    } finally {
        setLoading(false);
    }
});

function setLoading(isLoading) {
    fetchBtn.disabled = isLoading;
    btnText.style.display = isLoading ? 'none' : 'block';
    btnLoader.style.display = isLoading ? 'block' : 'none';
}

function displayInfo(data) {
    document.getElementById('video-title').textContent = data.title;
    document.getElementById('uploader').textContent = data.uploader;
    document.getElementById('duration').textContent = formatDuration(data.duration);
    document.getElementById('video-thumbnail').style.backgroundImage = `url(${data.thumbnail})`;
    
    formatList.innerHTML = '';
    data.formats.forEach(f => {
        const item = document.createElement('div');
        item.className = 'format-item';
        item.innerHTML = `
            <div>
                <strong>${f.ext.toUpperCase()}</strong> - ${f.resolution}
                <div style="font-size: 12px; opacity: 0.6;">${f.note}</div>
            </div>
            <span>${formatBytes(f.filesize)}</span>
        `;
        item.onclick = () => startDownload(data.url, f.id);
        formatList.appendChild(item);
    });

    resultContainer.style.display = 'block';
    selectionArea.style.display = 'block';
    downloadArea.style.display = 'none';
    finishBtnContainer.style.display = 'none';
}

async function startDownload(url, formatId) {
    selectionArea.style.display = 'none';
    downloadArea.style.display = 'block';
    
    try {
        const response = await fetch('/download', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url, format: formatId })
        });
        
        const data = await response.json();
        if (data.error) throw new Error(data.error);

        currentJobId = data.job_id;
        pollStatus();
    } catch (err) {
        alert('Erro no Download: ' + err.message);
        selectionArea.style.display = 'block';
        downloadArea.style.display = 'none';
    }
}

async function pollStatus() {
    if (!currentJobId) return;

    try {
        const response = await fetch(`/status/${currentJobId}`);
        const data = await response.json();

        if (data.status === 'Baixando') {
            const prog = parseFloat(data.progress) || 0;
            progressBar.style.width = prog + '%';
            statusText.textContent = `Baixando... ${prog}%`;
            speedText.textContent = data.speed;
            etaText.textContent = data.eta;
            setTimeout(pollStatus, 1000);
        } else if (data.status === 'Iniciando') {
            statusText.textContent = 'Iniciando...';
            setTimeout(pollStatus, 1000);
        } else if (data.status === 'Processando') {
            progressBar.style.width = '100%';
            statusText.textContent = 'Processando / Finalizando...';
            setTimeout(pollStatus, 1000);
        } else if (data.status === 'Concluído') {
            progressBar.style.width = '100%';
            statusText.textContent = 'Pronto!';
            speedText.textContent = '';
            etaText.textContent = '';
            showFinishButton();
        } else if (data.status === 'Erro') {
            alert('Erro no Trabalho: ' + data.error);
        }
    } catch (err) {
        console.error('Erro de polling:', err);
        setTimeout(pollStatus, 2000);
    }
}

function showFinishButton() {
    downloadLink.href = `/get_file/${currentJobId}`;
    finishBtnContainer.style.display = 'block';
    if (window.lucide) {
        window.lucide.createIcons();
    }
}

function resetUI() {
    resultContainer.style.display = 'none';
    urlInput.value = '';
    currentJobId = null;
}

// Utils
function formatDuration(seconds) {
    if (!seconds) return 'N/A';
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = seconds % 60;
    return [h, m, s]
        .map(v => v < 10 ? '0' + v : v)
        .filter((v, i) => v !== '00' || i > 0)
        .join(':');
}

function formatBytes(bytes, decimals = 2) {
    if (!bytes || bytes === 0) return 'Unknown size';
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
}
