/**
 * static/chat.js — Логика чат-бота AI Buyer Assistant.
 * Управляет диалогом с LLM, рендерит сообщения, обрабатывает ответы бота.
 */

(function () {
    "use strict";

    // ===== STATE =====
    let messages = []; // history of messages for API
    let isLoading = false;

    // ===== DOM ELEMENTS =====
    const chatMessages = document.getElementById("chatMessages");
    const chatForm = document.getElementById("chatForm");
    const chatInput = document.getElementById("chatInput");
    const sendBtn = document.getElementById("sendBtn");
    const chatResults = document.getElementById("chatResults");
    const chatResultsList = document.getElementById("chatResultsList");
    const welcomeMessage = document.getElementById("welcomeMessage");

    // ===== INIT =====
    // Check URL params for pre-filled text (from catalog click)
    (function checkUrlParams() {
        try {
            var params = new URLSearchParams(window.location.search);
            var text = params.get("text");
            if (text) {
                chatInput.value = decodeURIComponent(text);
                // Clear URL param
                window.history.replaceState({}, document.title, "/chat");
                // Auto-submit
                chatForm.dispatchEvent(new Event("submit"));
                return;
            }
        } catch (e) { /* ignore */ }

        // Fallback: check sessionStorage
        try {
            var stored = sessionStorage.getItem("chat_pretext");
            if (stored) {
                chatInput.value = stored;
                sessionStorage.removeItem("chat_pretext");
                chatForm.dispatchEvent(new Event("submit"));
            }
        } catch (e) { /* ignore */ }
    })();

    document.querySelectorAll(".chat__suggestion").forEach(function (btn) {
        btn.addEventListener("click", function () {
            var text = this.getAttribute("data-text");
            if (text) {
                chatInput.value = text;
                chatForm.dispatchEvent(new Event("submit"));
            }
        });
    });

    // ===== FORM SUBMIT =====
    chatForm.addEventListener("submit", function (e) {
        e.preventDefault();
        var text = chatInput.value.trim();
        if (!text || isLoading) return;

        // Hide welcome message on first user message
        if (welcomeMessage) {
            welcomeMessage.style.display = "none";
        }

        // Hide results area for new conversation
        chatResults.classList.remove("chat__results--visible");

        // Add user message to UI
        appendMessage("user", text);
        messages.push({ role: "user", text: text });

        // Clear input
        chatInput.value = "";
        chatInput.focus();

        // Send to API
        sendToAPI();
    });

    // ===== SEND TO API =====
    function sendToAPI() {
        isLoading = true;
        sendBtn.disabled = true;
        showTypingIndicator();

        fetch("/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ messages: messages }),
        })
            .then(function (res) { return res.json(); })
            .then(function (data) {
                hideTypingIndicator();
                if (data.error) {
                    appendMessage("bot", "❌ Ошибка: " + data.error);
                    messages.push({ role: "assistant", text: "Произошла ошибка при обработке запроса." });
                    return;
                }

                // Handle response based on status
                if (data.status === "ok") {
                    handleOkResponse(data);
                } else if (data.status === "clarify") {
                    handleClarifyResponse(data);
                } else if (data.status === "no_match") {
                    appendMessage("bot", data.message || "К сожалению, не удалось подобрать товары по заданным условиям.");
                    messages.push({ role: "assistant", text: data.message || "Не удалось подобрать товары." });
                } else {
                    appendMessage("bot", "Неизвестный статус ответа: " + data.status);
                }
            })
            .catch(function (err) {
                hideTypingIndicator();
                appendMessage("bot", "❌ Ошибка соединения: " + err.message);
            })
            .finally(function () {
                isLoading = false;
                sendBtn.disabled = false;
                chatInput.focus();
            });
    }

    // ===== HANDLE "OK" STATUS (options found) =====
    function handleOkResponse(data) {
        var options = data.options || [];
        if (options.length === 0) {
            appendMessage("bot", "Не удалось подобрать варианты.");
            return;
        }

        var responseText = "Найдено " + options.length + " вариант(ов):\n\n";
        appendMessage("bot", responseText);
        renderResults(options);
        messages.push({ role: "assistant", text: responseText });
    }

    // ===== HANDLE "CLARIFY" STATUS (need more info) =====
    function handleClarifyResponse(data) {
        var questions = data.questions || [];
        if (questions.length === 0) {
            appendMessage("bot", "Не понял ваш запрос. Уточните, пожалуйста.");
            return;
        }

        var textParts = ["Уточните, пожалуйста:"];
        questions.forEach(function (q) {
            textParts.push("• " + q.text);
        });

        var responseText = textParts.join("\n\n");
        appendMessage("bot", responseText);
        messages.push({ role: "assistant", text: responseText });
    }

    // ===== RENDER RESULTS =====
    function renderResults(options) {
        chatResults.classList.add("chat__results--visible");
        chatResultsList.innerHTML = "";

        options.forEach(function (option, index) {
            var el = document.createElement("div");
            el.className = "result-option";

            var totalRub = option.total_rub || 0;
            var explanation = option.explanation || "";
            var listingIds = option.listing_ids || [];

            var html = '<div class="result-option__header">';
            html += '<span class="result-option__price">' + formatPrice(totalRub) + ' ₽</span>';
            html += '<span class="result-option__count">Опция ' + (index + 1) + '</span>';
            html += '</div>';

            html += '<div class="result-option__items">';
            listingIds.forEach(function (id) {
                html += '<div class="result-option__item">';
                html += '<span class="result-option__item-icon"></span>';
                html += '<span>Товар #' + id + '</span>';
                html += '</div>';
            });
            html += '</div>';

            if (explanation) {
                html += '<div class="result-option__explanation">' + explanation + '</div>';
            }

            el.innerHTML = html;
            chatResultsList.appendChild(el);
        });

        // Кнопка для нового поиска
        var newSearchBtn = document.createElement("div");
        newSearchBtn.style.textAlign = "center";
        newSearchBtn.style.marginTop = "12px";
        newSearchBtn.style.marginBottom = "4px";
        newSearchBtn.innerHTML = '<button id="newSearchBtn" class="btn btn--secondary" style="padding: 8px 16px; font-size: 0.85rem;">🔄 Новый поиск</button>';
        chatResultsList.appendChild(newSearchBtn);

        // Добавляем обработчик на кнопку "Новый поиск"
        document.getElementById("newSearchBtn").addEventListener("click", function () {
            // Очистить историю
            messages = [];
            // Скрыть результаты
            chatResults.classList.remove("chat__results--visible");
            // Показать приветственное сообщение
            if (welcomeMessage) {
                welcomeMessage.style.display = "flex";
            }
            // Очистить сообщения
            chatMessages.innerHTML = "";
            // Сфокусировать на поле ввода
            chatInput.focus();
        });

        // Scroll to results
        setTimeout(function () {
            chatResults.scrollIntoView({ behavior: "smooth", block: "nearest" });
        }, 100);
    }

    // ===== APPEND MESSAGE TO CHAT =====
    function appendMessage(role, text) {
        var msgDiv = document.createElement("div");
        msgDiv.className = "chat__message chat__message--" + role;

        if (role === "bot") {
            var avatar = document.createElement("div");
            avatar.className = "chat__message-avatar chat__message-avatar--bot";
            avatar.innerHTML = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2">' +
                '<path d="M12 2a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z"></path>' +
                '<path d="M19 10v1a7 7 0 0 1-14 0v-1"></path>' +
                '<line x1="12" y1="18" x2="12" y2="22"></line>' +
                '<line x1="8" y1="22" x2="16" y2="22"></line>' +
                '</svg>';
            msgDiv.appendChild(avatar);
        }

        var content = document.createElement("div");
        content.className = "chat__message-content";

        // Convert newlines to <br>
        var formattedText = text.replace(/\n/g, "<br>");
        content.innerHTML = '<p>' + formattedText + '</p>';

        msgDiv.appendChild(content);
        chatMessages.appendChild(msgDiv);

        // Auto scroll to bottom
        var container = document.getElementById("chatContainer");
        container.scrollTop = container.scrollHeight;
    }

    // ===== TYPING INDICATOR =====
    var typingEl = null;

    function showTypingIndicator() {
        typingEl = document.createElement("div");
        typingEl.className = "chat__message chat__message--bot chat__message--typing";
        typingEl.innerHTML = '<div class="chat__message-avatar chat__message-avatar--bot"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2"><path d="M12 2a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z"></path><path d="M19 10v1a7 7 0 0 1-14 0v-1"></path></svg></div>' +
            '<div class="chat__message-content"><div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div></div>';
        chatMessages.appendChild(typingEl);

        var container = document.getElementById("chatContainer");
        container.scrollTop = container.scrollHeight;
    }

    function hideTypingIndicator() {
        if (typingEl && typingEl.parentNode) {
            typingEl.parentNode.removeChild(typingEl);
            typingEl = null;
        }
    }

    // ===== FORMAT PRICE =====
    function formatPrice(num) {
        return Number(num).toLocaleString("ru-RU");
    }

    // ===== RUSSIAN TRANSLATION DICTIONARY =====
    // Перевод английских терминов на русский (используется бэкендом в вопросах)
    var RUSSIAN_TRANSLATIONS = {
        // Категории
        "(table, chair, lamp)": "(стол, кресло, лампа)",
        "table": "стол",
        "chair": "кресло",
        "lamp": "лампа",
        
        // Поля
        "budget_rub": "бюджет",
        "city_id": "город",
        "categories": "категории",
        "constraints": "ограничения",
        
        // Вопросы бота
        "Какие категории товаров вас интересуют? (table, chair, lamp)": "Какие категории товаров вас интересуют? (стол, кресло, лампа)",
        "В каком городе вам нужен самовывоз? (taganrog, rostov-na-donu, azov)": "В каком городе вам нужен самовывоз? (Таганрог, Ростов-на-Дону, Азов)",
        "Какой у вас бюджет на весь комплект? (в рублях)": "Какой у вас бюджет на весь комплект? (в рублях)",
        
        // Сообщения об ошибках
        "in the city": "В городе",
        "there is no full set from": "нет полного комплекта из",
        "by budget": "по бюджету",
        "Try to increase the budget or change the composition of the kit": "Попробуйте увеличить бюджет или изменить состав комплекта",
        
        // Общие фразы
        "items": "товары",
        "option": "опция",
        "products": "товары",
    };

    // Функция перевода английских терминов на русский
    function translateEnglishToRussian(text) {
        if (!text) return text;
        
        var translated = text;
        
        // Сначала заменяем длинные фразы, чтобы не было конфликтов
        for (var key in RUSSIAN_TRANSLATIONS) {
            if (RUSSIAN_TRANSLATIONS.hasOwnProperty(key)) {
                var regex = new RegExp(key.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'g');
                translated = translated.replace(regex, RUSSIAN_TRANSLATIONS[key]);
            }
        }
        
        // Переводим отдельные слова в скобках
        translated = translated.replace(/\((table|chair|lamp)\)/g, function(match) {
            var words = match.replace(/[()]/g, '').split(',').map(function(w) {
                return RUSSIAN_TRANSLATIONS[w.trim()] || w.trim();
            });
            return '(' + words.join(', ') + ')';
        });
        
        return translated;
    }

    // ===== APPEND MESSAGE TO CHAT =====
    function appendMessage(role, text) {
        // Переводим на русский если это сообщение от бота
        if (role === "bot") {
            text = translateEnglishToRussian(text);
        }
        
        var msgDiv = document.createElement("div");
        msgDiv.className = "chat__message chat__message--" + role;

        if (role === "bot") {
            var avatar = document.createElement("div");
            avatar.className = "chat__message-avatar chat__message-avatar--bot";
            avatar.innerHTML = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2">' +
                '<path d="M12 2a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z"></path>' +
                '<path d="M19 10v1a7 7 0 0 1-14 0v-1"></path>' +
                '<line x1="12" y1="18" x2="12" y2="22"></line>' +
                '<line x1="8" y1="22" x2="16" y2="22"></line>' +
                '</svg>';
            msgDiv.appendChild(avatar);
        }

        var content = document.createElement("div");
        content.className = "chat__message-content";

        // Convert newlines to <br>
        var formattedText = text.replace(/\n/g, "<br>");
        content.innerHTML = '<p>' + formattedText + '</p>';

        msgDiv.appendChild(content);
        chatMessages.appendChild(msgDiv);

        // Auto scroll to bottom
        var container = document.getElementById("chatContainer");
        container.scrollTop = container.scrollHeight;
    }
})();
