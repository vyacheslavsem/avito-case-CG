/**
 * static/catalog.js — Логика страницы каталога.
 * Загружает товары, применяет фильтры, рендерит карточки.
 */

(function () {
    "use strict";

    // ===== DOM ELEMENTS =====
    var catalogGrid = document.getElementById("catalogGrid");
    var catalogCount = document.getElementById("catalogCount");
    var catalogEmpty = document.getElementById("catalogEmpty");
    var filterCategory = document.getElementById("filterCategory");
    var minPriceInput = document.getElementById("minPrice");
    var maxPriceInput = document.getElementById("maxPrice");
    var applyFiltersBtn = document.getElementById("applyFilters");
    var resetFiltersBtn = document.getElementById("resetFilters");
    var citySelect = document.getElementById("citySelect");

    // ===== CATEGORIES & CITIES CACHE =====
    var allListings = [];
    var categories = [];
    var isLoading = false;

    // ===== NOTIFICATIONS =====
    function showNotification(message, type) {
        var existing = document.querySelector(".notification");
        if (existing) existing.remove();

        var notification = document.createElement("div");
        notification.className = "notification notification--" + type;
        notification.textContent = message;
        document.body.appendChild(notification);

        setTimeout(function () {
            notification.style.animation = "fadeOut 0.3s ease-out";
            setTimeout(function () {
                if (notification.parentNode) notification.remove();
            }, 300);
        }, 4000);
    }

    // ===== INIT =====
    function init() {
        loadCities();
        loadCatalog();
        setupEventListeners();
    }

    function setupEventListeners() {
        applyFiltersBtn.addEventListener("click", applyFilters);
        resetFiltersBtn.addEventListener("click", resetFilters);

        // City change — reload catalog
        if (citySelect) {
            citySelect.addEventListener("change", applyFilters);
        }

        // Category change — reload catalog
        if (filterCategory) {
            filterCategory.addEventListener("change", applyFilters);
        }

        // Enter key on price inputs
        if (minPriceInput) {
            minPriceInput.addEventListener("keydown", function (e) {
                if (e.key === "Enter") applyFilters();
            });
        }
        if (maxPriceInput) {
            maxPriceInput.addEventListener("keydown", function (e) {
                if (e.key === "Enter") applyFilters();
            });
        }
    }

    // ===== LOAD CITIES =====
    function loadCities() {
        if (!citySelect) return;

        fetch("/api/cities")
            .then(function (res) { return res.json(); })
            .then(function (data) {
                data.forEach(function (city) {
                    var option = document.createElement("option");
                    // API возвращает объекты {id, name} или строки
                    option.value = city.id || city;
                    option.textContent = city.name || formatCity(city.id || city);
                    citySelect.appendChild(option);
                });
            })
            .catch(function () {
                // Fallback
                var cities = ["taganrog", "rostov-na-donu", "azov"];
                cities.forEach(function (city) {
                    var option = document.createElement("option");
                    option.value = city;
                    option.textContent = formatCity(city);
                    citySelect.appendChild(option);
                });
            });
    }

    // ===== LOAD CATALOG =====
    function loadCatalog() {
        if (isLoading) return;
        isLoading = true;

        var params = new URLSearchParams();
        var city = citySelect ? citySelect.value : "";
        if (city) params.set("city", city);

        console.log("Loading catalog with params:", params.toString());

        fetch("/api/catalog?" + params.toString())
            .then(function (res) {
                console.log("Response status:", res.status);
                if (!res.ok) throw new Error("HTTP " + res.status);
                return res.json();
            })
            .then(function (data) {
                console.log("Catalog data received:", data);
                allListings = data.listings || [];
                console.log("Listings count:", allListings.length);
                categories = data.categories || [];
                console.log("Categories count:", categories.length);
                populateCategories();
                renderListings(allListings);
                if (allListings.length > 0) {
                    showNotification("Загружено " + allListings.length + " товаров", "success");
                }
            })
            .catch(function (err) {
                console.error("Failed to load catalog:", err);
                if (catalogCount) catalogCount.textContent = "Ошибка загрузки";
                showNotification("Не удалось загрузить каталог: " + err.message, "error");
            })
            .finally(function () {
                isLoading = false;
            });
    }

    // ===== POPULATE CATEGORIES =====
    function populateCategories() {
        if (!filterCategory) return;

        categories.forEach(function (cat) {
            var value, label;
            if (typeof cat === "object") {
                value = cat.id || cat.name || "";
                label = cat.name || cat.title || cat.id || "Без категории";
            } else {
                value = cat;
                label = cat;
            }

            var option = document.createElement("option");
            option.value = value;
            option.textContent = label;
            filterCategory.appendChild(option);
        });
    }

    // ===== APPLY FILTERS =====
    function applyFilters() {
        var city = citySelect ? citySelect.value : "";
        var category = filterCategory ? filterCategory.value : "";
        var minPrice = minPriceInput ? minPriceInput.value : "";
        var maxPrice = maxPriceInput ? maxPriceInput.value : "";

        var filtered = allListings.filter(function (item) {
            if (city && item.city_id !== city) return false;
            if (category && item.category !== category) return false;

            var price = item.price_rub || 0;
            // обе границы включительно: price_from <= price <= price_to
            if (minPrice && price < parseFloat(minPrice)) return false;
            if (maxPrice && price > parseFloat(maxPrice)) return false;

            return true;
        });

        renderListings(filtered);
    }

    // ===== RESET FILTERS =====
    function resetFilters() {
        // Дать браузеру сбросить форму
        setTimeout(function () {
            if (citySelect) citySelect.value = "";
            if (filterCategory) filterCategory.value = "";
            if (minPriceInput) minPriceInput.value = "";
            if (maxPriceInput) maxPriceInput.value = "";
            renderListings(allListings);
        }, 0);
    }

    // ===== RENDER LISTINGS =====
    function renderListings(listings) {
        if (!catalogGrid) {
            console.error("catalogGrid element not found!");
            return;
        }

        catalogGrid.innerHTML = "";
        catalogCount.textContent = listings.length + " товаров";

        if (listings.length === 0) {
            catalogEmpty.style.display = "block";
            return;
        }

        catalogEmpty.style.display = "none";

        console.log("Rendering", listings.length, "listings");

        listings.forEach(function (item) {
            var card = document.createElement("div");
            card.className = "product-card";

            var categoryBadge = getCategoryLabel(item.category);
            var price = formatPrice(item.price_rub);
            var city = formatCity(item.city_id);
            var title = item.title || "Без названия";
            var desc = item.description || "";
            var categoryId = item.category || "";

            console.log("Creating card:", title, "Price:", price, "City:", city);

            var html = '<div class="product-card__image">📦</div>';
            html += '<div class="product-card__body">';
            html += '<span class="product-card__category-badge">' + categoryBadge + '</span>';
            html += '<h3 class="product-card__title">' + escapeHtml(title) + '</h3>';
            html += '<p class="product-card__desc">' + escapeHtml(desc) + '</p>';
            html += '<div class="product-card__price">' + price + ' ₽</div>';
            html += '<div class="product-card__city">📍 ' + city + '</div>';
            html += '</div>';

            card.innerHTML = html;

            // Click → go to chat with this item info
            card.addEventListener("click", function () {
                goToChatWithItem(item);
            });

            catalogGrid.appendChild(card);
        });

        console.log("Cards created. Grid children:", catalogGrid.children.length);
    }

    // ===== GO TO CHAT WITH ITEM =====
    function goToChatWithItem(item) {
        if (window.location.pathname !== "/") {
            // Already on chat page — just scroll
            return;
        }

        var text = "Покажи товар: " + (item.title || "") + " (категория: " + (item.category || "") + ", город: " + (item.city_id || "") + ")";
        window.location.href = "/chat?text=" + encodeURIComponent(text);
    }

    // ===== FORMAT HELPERS =====
    function formatPrice(num) {
        return Number(num).toLocaleString("ru-RU");
    }

    function formatCity(cityId) {
        var labels = {
            "taganrog": "Таганрог",
            "rostov-na-donu": "Ростов-на-Дону",
            "azov": "Азов"
        };
        return labels[cityId] || cityId || "";
    }

    function getCategoryLabel(catId) {
        var labels = {
            "table": "Стол",
            "chair": "Кресло",
            "lamp": "Лампа"
        };
        return labels[catId] || catId || "Товар";
    }

    function escapeHtml(str) {
        var div = document.createElement("div");
        div.textContent = str;
        return div.innerHTML;
    }

    // ===== CHECK URL PARAMS (pre-filled chat text) =====
    function checkUrlParams() {
        var params = new URLSearchParams(window.location.search);
        var text = params.get("text");
        if (text && window.location.pathname === "/chat") {
            // Will be handled by chat.js — store in sessionStorage
            try {
                sessionStorage.setItem("chat_pretext", text);
            } catch (e) { /* ignore */ }
        }
    }

    // ===== BOOT =====
    init();
    checkUrlParams();
})();
