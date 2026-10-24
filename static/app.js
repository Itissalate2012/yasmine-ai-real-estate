/**
 * app.js - Client frontend pour l'Agent Immobilier Vocal & Réfléchi Yasmine
 * Gestion des messages écrits, de l'enregistrement vocal, de la lecture des notes vocales,
 * de l'affichage des cartes d'appartements et de la réflexion cognitive.
 */

const state = {
    conversationHistory: [],
    selectedLanguage: 'auto',
    isRecording: false,
    mediaRecorder: null,
    audioChunks: [],
    recordStartTime: null,
    recordTimerInterval: null,
    currentPlayingAudio: null,
    allProperties: []
};

const chatMessages = document.getElementById('chat-messages');
const chatInput = document.getElementById('chat-input');
const btnSendText = document.getElementById('btn-send-text');
const btnMic = document.getElementById('btn-mic');
const recordingBar = document.getElementById('recording-bar');
const recTimer = document.getElementById('rec-timer');
const btnCancelRecording = document.getElementById('btn-cancel-recording');
const btnSendRecording = document.getElementById('btn-send-recording');
const langSelect = document.getElementById('lang-select');
const btnToggleCatalog = document.getElementById('btn-toggle-catalog');
const catalogDrawer = document.getElementById('catalog-drawer');
const drawerBackdrop = document.getElementById('drawer-backdrop');
const btnCloseDrawer = document.getElementById('btn-close-drawer');
const drawerItems = document.getElementById('drawer-items');
const filterProject = document.getElementById('filter-project');
const filterTypology = document.getElementById('filter-typology');
const imageModal = document.getElementById('image-modal');
const modalImg = document.getElementById('modal-img');
const modalCaption = document.getElementById('modal-caption');
const btnCloseModal = document.getElementById('btn-close-modal');

document.addEventListener('DOMContentLoaded', () => {
    initEventListeners();
    loadCatalogData();
    autoResizeTextarea();
});

function initEventListeners() {
    btnSendText.addEventListener('click', handleSendTextMessage);
    chatInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSendTextMessage();
        }
    });

    btnMic.addEventListener('click', startAudioRecording);
    btnCancelRecording.addEventListener('click', cancelAudioRecording);
    btnSendRecording.addEventListener('click', stopAndSendAudioRecording);

    langSelect.addEventListener('change', (e) => {
        state.selectedLanguage = e.target.value;
    });

    document.querySelectorAll('.chip').forEach(chip => {
        chip.addEventListener('click', () => {
            const query = chip.getAttribute('data-query');
            if (query) {
                chatInput.value = query;
                handleSendTextMessage();
            }
        });
    });

    btnToggleCatalog.addEventListener('click', openCatalogDrawer);
    btnCloseDrawer.addEventListener('click', closeCatalogDrawer);
    drawerBackdrop.addEventListener('click', closeCatalogDrawer);
    filterProject.addEventListener('change', renderCatalogDrawerItems);
    filterTypology.addEventListener('change', renderCatalogDrawerItems);

    btnCloseModal.addEventListener('click', () => imageModal.classList.add('hidden'));
    imageModal.addEventListener('click', (e) => {
        if (e.target === imageModal) imageModal.classList.add('hidden');
    });
}

function autoResizeTextarea() {
    chatInput.addEventListener('input', () => {
        chatInput.style.height = 'auto';
        chatInput.style.height = Math.min(chatInput.scrollHeight, 120) + 'px';
    });
}

async function handleSendTextMessage() {
    const text = chatInput.value.trim();
    if (!text) return;

    appendUserMessage(text, 'text');
    chatInput.value = '';
    chatInput.style.height = 'auto';

    const loadingElem = appendLoadingMessage();

    try {
        const response = await fetch('/api/chat/text', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: text,
                conversation_history: state.conversationHistory,
                language: state.selectedLanguage
            })
        });

        if (!response.ok) throw new Error('Erreur lors de la réponse du serveur');
        const data = await response.json();

        loadingElem.remove();
        appendAgentResponse(data, 'text');

        state.conversationHistory.push({ role: 'user', text: text });
        state.conversationHistory.push({ role: 'agent', text: data.response_text });

    } catch (err) {
        console.error(err);
        loadingElem.remove();
        appendErrorMessage("Désolée, une difficulté technique est survenue. Veuillez réessayer.");
    }
}

async function startAudioRecording() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        state.audioChunks = [];
        
        const options = { mimeType: 'audio/webm' };
        if (!MediaRecorder.isTypeSupported('audio/webm')) {
            delete options.mimeType;
        }

        state.mediaRecorder = new MediaRecorder(stream, options);

        state.mediaRecorder.ondataavailable = (event) => {
            if (event.data && event.data.size > 0) {
                state.audioChunks.push(event.data);
            }
        };

        state.mediaRecorder.start();
        state.isRecording = true;
        state.recordStartTime = Date.now();

        recordingBar.classList.remove('hidden');
        recTimer.textContent = '00:00';

        state.recordTimerInterval = setInterval(() => {
            const elapsed = Math.floor((Date.now() - state.recordStartTime) / 1000);
            const mins = String(Math.floor(elapsed / 60)).padStart(2, '0');
            const secs = String(elapsed % 60).padStart(2, '0');
            recTimer.textContent = `${mins}:${secs}`;
        }, 1000);

    } catch (err) {
        console.error('Erreur accès microphone:', err);
        alert("Impossible d'accéder au microphone. Veuillez autoriser l'accès audio dans votre navigateur.");
    }
}

function cancelAudioRecording() {
    if (state.mediaRecorder && state.isRecording) {
        state.mediaRecorder.stop();
        cleanupRecordingStream();
    }
    clearInterval(state.recordTimerInterval);
    recordingBar.classList.add('hidden');
    state.isRecording = false;
    state.audioChunks = [];
}

function stopAndSendAudioRecording() {
    if (!state.mediaRecorder || !state.isRecording) return;

    state.mediaRecorder.onstop = async () => {
        cleanupRecordingStream();
        clearInterval(state.recordTimerInterval);
        recordingBar.classList.add('hidden');
        state.isRecording = false;

        const audioBlob = new Blob(state.audioChunks, { type: 'audio/webm' });
        if (audioBlob.size < 500) {
            console.warn("Audio trop court.");
            return;
        }

        appendUserMessage("Message vocal envoyé (En cours de transcription...)", 'voice', audioBlob);

        const loadingElem = appendLoadingMessage("Yasmine écoute et réfléchit à votre demande...");

        try {
            const formData = new FormData();
            formData.append('audio_file', audioBlob, 'client_voice.webm');
            formData.append('conversation_history', JSON.stringify(state.conversationHistory));
            formData.append('language', state.selectedLanguage);

            const res = await fetch('/api/chat/audio', {
                method: 'POST',
                body: formData
            });

            if (!res.ok) throw new Error('Erreur traitement audio');
            const data = await res.json();

            loadingElem.remove();

            if (data.client_transcription) {
                updateLastUserVoiceText(data.client_transcription);
            }

            appendAgentResponse(data, 'voice');

            state.conversationHistory.push({ role: 'user', text: data.client_transcription || "Message vocal" });
            state.conversationHistory.push({ role: 'agent', text: data.response_text });

        } catch (err) {
            console.error(err);
            loadingElem.remove();
            appendErrorMessage("Désolée, je n'ai pas pu analyser l'enregistrement audio.");
        }
    };

    state.mediaRecorder.stop();
}

function cleanupRecordingStream() {
    if (state.mediaRecorder && state.mediaRecorder.stream) {
        state.mediaRecorder.stream.getTracks().forEach(track => track.stop());
    }
}

function appendUserMessage(text, modality = 'text', audioBlob = null) {
    const row = document.createElement('div');
    row.className = 'message-row user-row';

    const isVoice = modality === 'voice';
    let voicePlayerHtml = '';
    if (isVoice && audioBlob) {
        const audioUrl = URL.createObjectURL(audioBlob);
        voicePlayerHtml = `
            <div class="voice-note-player user-voice-player">
                <button class="btn-play-pause" onclick="playAudioBlob(this, '${audioUrl}')">
                    <i class="fa-solid fa-play"></i>
                </button>
                <div class="waveform-container">
                    <span class="waveform-bar"></span>
                    <span class="waveform-bar"></span>
                    <span class="waveform-bar"></span>
                    <span class="waveform-bar"></span>
                    <span class="waveform-bar"></span>
                    <span class="waveform-bar"></span>
                    <span class="waveform-bar"></span>
                </div>
                <span class="audio-duration">Vocal</span>
            </div>
        `;
    }

    row.innerHTML = `
        <div class="message-content">
            <div class="bubble user-bubble">
                <div class="bubble-header">
                    <span>Vous</span>
                    <span>${getCurrentTime()}</span>
                </div>
                ${voicePlayerHtml}
                <div class="bubble-text user-voice-transcription">
                    <p>${escapeHtml(text)}</p>
                </div>
            </div>
        </div>
    `;

    chatMessages.appendChild(row);
    scrollToBottom();
}

function updateLastUserVoiceText(transcription) {
    const transcriptions = document.querySelectorAll('.user-voice-transcription p');
    if (transcriptions.length > 0) {
        const last = transcriptions[transcriptions.length - 1];
        last.innerHTML = `<em>"${escapeHtml(transcription)}"</em>`;
    }
}

function appendAgentResponse(data, modality = 'text') {
    const row = document.createElement('div');
    row.className = 'message-row agent-row';

    let thinkingHtml = '';
    if (data.thinking) {
        const isAr = data.language === 'ar';
        const title = isAr ? '🧠 تفكير وتحليل المستشارة ياسمين (اضغط للعرض)' : '🧠 Réflexion & Analyse de Yasmine (Cliquez pour afficher)';
        thinkingHtml = `
            <div class="thinking-accordion collapsed">
                <div class="thinking-header" onclick="toggleThinking(this)">
                    <span><i class="fa-solid fa-brain"></i> ${title}</span>
                    <i class="fa-solid fa-chevron-down arrow-icon"></i>
                </div>
                <div class="thinking-body" dir="${isAr ? 'rtl' : 'ltr'}">
                    ${escapeHtml(data.thinking)}
                </div>
            </div>
        `;
    }

    let voicePlayerHtml = '';
    if (data.audio_url || modality === 'voice') {
        const audioSrc = data.audio_url || '';
        voicePlayerHtml = `
            <div class="voice-note-player" data-audiosrc="${audioSrc}">
                <button class="btn-play-pause" onclick="toggleVoiceNote(this, '${audioSrc}', '${escapeHtml(data.audio_script || data.response_text)}')">
                    <i class="fa-solid fa-play"></i>
                </button>
                <div class="waveform-container">
                    <span class="waveform-bar"></span>
                    <span class="waveform-bar"></span>
                    <span class="waveform-bar"></span>
                    <span class="waveform-bar"></span>
                    <span class="waveform-bar"></span>
                    <span class="waveform-bar"></span>
                    <span class="waveform-bar"></span>
                    <span class="waveform-bar"></span>
                    <span class="waveform-bar"></span>
                </div>
                <span class="audio-duration">🎙️ Voix</span>
            </div>
        `;
    }

    let cardsHtml = '';
    if (data.apartment_cards && data.apartment_cards.length > 0) {
        cardsHtml = renderApartmentCards(data.apartment_cards, data.language);
    }

    let projectsHtml = '';
    if (data.project_cards && data.project_cards.length > 0) {
        projectsHtml = renderProjectCards(data.project_cards, data.language);
    }

    const isArabic = data.language === 'ar';
    const textFormatted = formatAgentText(data.response_text);

    row.innerHTML = `
        <div class="avatar-col">
            <img src="https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?auto=format&fit=crop&w=200&q=80" class="mini-avatar" alt="Yasmine">
        </div>
        <div class="message-content">
            ${thinkingHtml}
            <div class="bubble agent-bubble">
                <div class="bubble-header">
                    <span class="sender-name">Yasmine | ياسمين</span>
                    <span class="message-time">${getCurrentTime()}</span>
                </div>
                ${voicePlayerHtml}
                <div class="bubble-text ${isArabic ? 'arabic-p' : ''}" dir="${isArabic ? 'rtl' : 'ltr'}">
                    ${textFormatted}
                </div>
            </div>
            ${cardsHtml}
            ${projectsHtml}
        </div>
    `;

    chatMessages.appendChild(row);
    scrollToBottom();

    if (modality === 'voice' && data.audio_url) {
        const btnPlay = row.querySelector('.btn-play-pause');
        if (btnPlay) {
            setTimeout(() => {
                toggleVoiceNote(btnPlay, data.audio_url, data.audio_script);
            }, 400);
        }
    }
}

function renderApartmentCards(apartments, lang = 'fr') {
    const isAr = lang === 'ar';
    let html = `<div class="property-cards-container">`;

    apartments.forEach(apt => {
        const title = isAr ? apt.title_ar : apt.title_fr;
        const discount = isAr ? apt.special_discount_ar : apt.special_discount_fr;
        const mainPhoto = (apt.photos && apt.photos.length > 0) ? apt.photos[0] : '';
        const floorplan = apt.floorplan_image || '';

        html += `
            <div class="property-card" data-apt-id="${apt.id}">
                <div class="card-img-wrapper" onclick="openImageModal('${mainPhoto}', '${escapeHtml(title)}')">
                    <img src="${mainPhoto}" alt="${escapeHtml(title)}" loading="lazy">
                    <span class="badge-status">${apt.status}</span>
                    <span class="badge-typology">${apt.typology}</span>
                </div>
                <div class="card-body">
                    <div class="card-title" dir="${isAr ? 'rtl' : 'ltr'}">${escapeHtml(title)}</div>
                    <div class="card-project-sub">${escapeHtml(apt.project_name)}</div>
                    <div class="card-specs">
                        <span><i class="fa-solid fa-ruler-combined"></i> ${apt.surface_m2} m²</span>
                        <span><i class="fa-solid fa-layer-group"></i> ${apt.floor}</span>
                        <span><i class="fa-regular fa-compass"></i> ${apt.orientation}</span>
                    </div>
                    <div class="card-price-row">
                        <span class="price-main">${apt.price_mad.toLocaleString()} MAD</span>
                        <span class="price-eur">~${apt.price_eur.toLocaleString()} €</span>
                    </div>
                    <div class="card-offer-banner">
                        <i class="fa-solid fa-tag"></i>
                        <span>${escapeHtml(discount)}</span>
                    </div>
                    <div class="card-actions">
                        <button class="btn-card-action" onclick="openImageModal('${floorplan}', 'Plan d\'architecte - ${escapeHtml(title)}')">
                            <i class="fa-solid fa-map"></i> Plan 2D/3D
                        </button>
                        <button class="btn-card-action" onclick="askAboutProperty('${apt.id}', '${escapeHtml(title)}')">
                            <i class="fa-solid fa-calendar-check"></i> Réserver visite
                        </button>
                    </div>
                </div>
            </div>
        `;
    });

    html += `</div>`;
    return html;
}

function renderProjectCards(projects, lang = 'fr') {
    if (!projects || projects.length === 0) return '';
    const isAr = lang === 'ar';
    let html = '<div class="project-cards-container">';
    projects.forEach(p => {
        const title = p.name;
        const tagline = isAr ? (p.tagline_ar || p.tagline_fr) : p.tagline_fr;
        const city = p.city;
        const delivery = p.delivery_date;
        const gallery = p.gallery || [
            { url: p.hero_image, caption_fr: p.name, caption_ar: p.name }
        ];

        html += `
            <div class="project-gallery-card">
                <div class="project-card-header">
                    <div>
                        <h4 class="project-title"><i class="fa-solid fa-city"></i> ${escapeHtml(title)}</h4>
                        <span class="project-tagline">${escapeHtml(tagline)}</span>
                    </div>
                    <span class="project-badge"><i class="fa-solid fa-location-dot"></i> ${escapeHtml(city)}</span>
                </div>
                <div class="project-gallery-grid">
                    ${gallery.map(img => `
                        <div class="gallery-item" onclick="openImageModal('${img.url}', '${escapeHtml(isAr ? (img.caption_ar || img.caption_fr) : img.caption_fr)}')">
                            <img src="${img.url}" alt="${escapeHtml(title)}" loading="lazy">
                            <div class="gallery-overlay">
                                <span><i class="fa-solid fa-magnifying-glass-plus"></i> ${escapeHtml(isAr ? (img.caption_ar || img.caption_fr) : img.caption_fr)}</span>
                            </div>
                        </div>
                    `).join('')}
                </div>
                <div class="project-card-footer">
                    <span><i class="fa-solid fa-calendar-check"></i> ${isAr ? 'موعد التسليم : ' : 'Livraison : '}<strong>${escapeHtml(delivery)}</strong></span>
                    <button class="btn-card-action" onclick="askAboutProjectUnits('${p.id}', '${escapeHtml(title)}')">
                        <i class="fa-solid fa-key"></i> ${isAr ? 'عرض الشقق المتاحة' : 'Voir les appartements disponibles'}
                    </button>
                </div>
            </div>
        `;
    });
    html += '</div>';
    return html;
}

function askAboutProjectUnits(projectId, projectName) {
    chatInput.value = `Quels sont les appartements disponibles au projet ${projectName} ?`;
    handleSendTextMessage();
}

function appendLoadingMessage(label = "Yasmine réfléchit à vos critères...") {
    const row = document.createElement('div');
    row.className = 'message-row agent-row loading-row';
    row.innerHTML = `
        <div class="avatar-col">
            <img src="https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?auto=format&fit=crop&w=200&q=80" class="mini-avatar" alt="Yasmine">
        </div>
        <div class="message-content">
            <div class="bubble agent-bubble">
                <div class="bubble-header">
                    <span>Yasmine</span>
                </div>
                <div class="typing-indicator">
                    <span class="typing-dot"></span>
                    <span class="typing-dot"></span>
                    <span class="typing-dot"></span>
                    <span style="font-size:0.8rem; color:#94a3b8; margin-left:6px;">${label}</span>
                </div>
            </div>
        </div>
    `;
    chatMessages.appendChild(row);
    scrollToBottom();
    return row;
}

function appendErrorMessage(msg) {
    const row = document.createElement('div');
    row.className = 'message-row agent-row';
    row.innerHTML = `
        <div class="avatar-col">
            <img src="https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?auto=format&fit=crop&w=200&q=80" class="mini-avatar" alt="Yasmine">
        </div>
        <div class="message-content">
            <div class="bubble agent-bubble" style="border-color:#ef4444;">
                <p style="color:#fca5a5;"><i class="fa-solid fa-circle-exclamation"></i> ${escapeHtml(msg)}</p>
            </div>
        </div>
    `;
    chatMessages.appendChild(row);
    scrollToBottom();
}

function toggleVoiceNote(button, audioUrl, fallbackText) {
    const player = button.closest('.voice-note-player');
    const icon = button.querySelector('i');

    if (state.currentPlayingAudio) {
        state.currentPlayingAudio.pause();
        const prevPlayer = state.currentPlayingAudio._playerElem;
        if (prevPlayer) {
            prevPlayer.classList.remove('playing');
            const prevIcon = prevPlayer.querySelector('.btn-play-pause i');
            if (prevIcon) {
                prevIcon.className = 'fa-solid fa-play';
            }
        }
        if (state.currentPlayingAudio._audioUrl === audioUrl && !state.currentPlayingAudio.paused) {
            state.currentPlayingAudio = null;
            return;
        }
    }

    if (audioUrl) {
        const audio = new Audio(audioUrl);
        audio._playerElem = player;
        audio._audioUrl = audioUrl;

        player.classList.add('playing');
        icon.className = 'fa-solid fa-pause';

        audio.play().catch(e => {
            console.warn("Échec lecture fichier audio, tentative Web Speech fallback:", e);
            speakWebSpeech(fallbackText, player, icon);
        });

        audio.onended = () => {
            player.classList.remove('playing');
            icon.className = 'fa-solid fa-play';
            state.currentPlayingAudio = null;
        };

        state.currentPlayingAudio = audio;
    } else {
        speakWebSpeech(fallbackText, player, icon);
    }
}

function speakWebSpeech(text, player, icon) {
    if (!('speechSynthesis' in window)) return;
    window.speechSynthesis.cancel();

    const utterance = new SpeechSynthesisUtterance(text);
    const isArabic = /[\u0600-\u06FF]/.test(text);
    utterance.lang = isArabic ? 'ar-SA' : 'fr-FR';

    const voices = window.speechSynthesis.getVoices();
    const femaleVoice = voices.find(v => 
        (isArabic ? v.lang.startsWith('ar') : v.lang.startsWith('fr')) &&
        (v.name.includes('Female') || v.name.includes('Amelie') || v.name.includes('Julie') || v.name.includes('Salma') || v.name.includes('Zari') || v.name.includes('Hoda'))
    );
    if (femaleVoice) utterance.voice = femaleVoice;

    player.classList.add('playing');
    icon.className = 'fa-solid fa-pause';

    utterance.onend = () => {
        player.classList.remove('playing');
        icon.className = 'fa-solid fa-play';
    };

    window.speechSynthesis.speak(utterance);
}

function playAudioBlob(button, url) {
    const audio = new Audio(url);
    const icon = button.querySelector('i');
    icon.className = 'fa-solid fa-pause';
    audio.play();
    audio.onended = () => {
        icon.className = 'fa-solid fa-play';
    };
}

async function loadCatalogData() {
    try {
        const res = await fetch('/api/properties');
        if (!res.ok) return;
        const data = await res.json();
        state.allProperties = data.apartments || [];
        
        if (data.projects) {
            data.projects.forEach(p => {
                const opt = document.createElement('option');
                opt.value = p.id;
                opt.textContent = p.name;
                filterProject.appendChild(opt);
            });
        }
        renderCatalogDrawerItems();
    } catch (e) {
        console.error("Erreur chargement catalogue:", e);
    }
}

function openCatalogDrawer() {
    catalogDrawer.classList.add('open');
    drawerBackdrop.classList.add('show');
}

function closeCatalogDrawer() {
    catalogDrawer.classList.remove('open');
    drawerBackdrop.classList.remove('show');
}

function renderCatalogDrawerItems() {
    const selectedProj = filterProject.value;
    const selectedTypo = filterTypology.value;

    let filtered = state.allProperties;
    if (selectedProj) filtered = filtered.filter(a => a.project_id === selectedProj);
    if (selectedTypo) filtered = filtered.filter(a => a.typology.includes(selectedTypo));

    drawerItems.innerHTML = '';
    if (filtered.length === 0) {
        drawerItems.innerHTML = '<p style="color:#94a3b8; text-align:center;">Aucun lot correspondant.</p>';
        return;
    }

    filtered.forEach(apt => {
        const card = document.createElement('div');
        card.className = 'property-card';
        card.innerHTML = `
            <div class="card-img-wrapper" onclick="openImageModal('${apt.photos[0]}', '${escapeHtml(apt.title_fr)}')">
                <img src="${apt.photos[0]}" alt="${apt.title_fr}">
                <span class="badge-status">${apt.status}</span>
                <span class="badge-typology">${apt.typology}</span>
            </div>
            <div class="card-body">
                <div class="card-title">${apt.title_fr}</div>
                <div class="card-project-sub">${apt.project_name}</div>
                <div class="card-specs">
                    <span>${apt.surface_m2} m²</span>
                    <span>${apt.floor}</span>
                    <span>${apt.orientation}</span>
                </div>
                <div class="card-price-row">
                    <span class="price-main">${apt.price_mad.toLocaleString()} MAD</span>
                    <span class="price-eur">~${apt.price_eur.toLocaleString()} €</span>
                </div>
                <button class="btn-card-action" style="margin-top:10px;" onclick="askAboutProperty('${apt.id}', '${escapeHtml(apt.title_fr)}')">
                    <i class="fa-regular fa-comment-dots"></i> Poser une question sur ce bien
                </button>
            </div>
        `;
        drawerItems.appendChild(card);
    });
}

function askAboutProperty(aptId, title) {
    closeCatalogDrawer();
    chatInput.value = `Pouvez-vous me donner plus de détails sur le bien "${title}" (réf: ${aptId}), son plan et ses modalités de paiement ?`;
    handleSendTextMessage();
}

function openImageModal(imgUrl, caption) {
    modalImg.src = imgUrl;
    modalCaption.textContent = caption || '';
    imageModal.classList.remove('hidden');
}

function toggleThinking(headerElem) {
    const accordion = headerElem.closest('.thinking-accordion');
    accordion.classList.toggle('collapsed');
}

function formatAgentText(text) {
    if (!text) return '';
    let formatted = escapeHtml(text);
    formatted = formatted.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    formatted = formatted.replace(/\n/g, '<br>');
    return formatted;
}

function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function getCurrentTime() {
    const now = new Date();
    return now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function scrollToBottom() {
    setTimeout(() => {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }, 50);
}
