(function () {
    const cartStorageKey = 'geberitCartItems';

    function getCartCount() {
        try {
            const items = JSON.parse(localStorage.getItem(cartStorageKey)) || [];
            return items.reduce((sum, item) => sum + (item.quantity || 0), 0);
        } catch (error) {
            return 0;
        }
    }

    function ensureStyle() {
        if (document.getElementById('cart-nav-style')) return;

        const style = document.createElement('style');
        style.id = 'cart-nav-style';
        style.textContent = `
            .cart-nav-link {
                display: inline-flex;
                align-items: center;
                justify-content: center;
                gap: 0.38rem;
                min-width: 2.1rem;
            }

            .cart-nav-icon {
                display: inline-flex;
                width: 1.45rem;
                height: 1.45rem;
                color: #111;
                line-height: 1;
            }

            .cart-nav-icon svg {
                width: 100%;
                height: 100%;
                display: block;
                stroke: currentColor;
                stroke-width: 2.5;
                stroke-linecap: round;
                stroke-linejoin: round;
            }

            .cart-nav-count {
                display: none;
                align-items: center;
                justify-content: center;
                min-width: 1.35rem;
                height: 1.35rem;
                border-radius: 999px;
                padding: 0 0.35rem;
                background: #3f6f8f;
                color: #fff;
                font-size: 0.78rem;
                font-weight: 900;
            }

            .cart-nav-link.has-items .cart-nav-count {
                display: inline-flex;
            }
        `;
        document.head.appendChild(style);
    }

    function getCartIcon() {
        return `
            <span class="cart-nav-icon" aria-hidden="true">
                <svg viewBox="0 0 24 24" fill="none">
                    <path d="M3 4h2l2.2 11.2a2 2 0 0 0 2 1.6h7.7a2 2 0 0 0 1.9-1.4L21 8H7"></path>
                    <path d="M9 20h.01"></path>
                    <path d="M17 20h.01"></path>
                    <path d="M9 11h10"></path>
                    <path d="M10 14h8"></path>
                </svg>
            </span>
        `;
    }

    function updateCartNavigation() {
        ensureStyle();
        const count = getCartCount();
        const links = document.querySelectorAll('a[href$="warenkorb.html"], a[href*="warenkorb.html"]');

        links.forEach((link, index) => {
            if (!link.classList.contains('cart-nav-link')) {
                link.classList.add('cart-nav-link');
            }

            const countId = link.id === 'cartNavLink' ? ' id="cartNavCount"' : '';
            link.innerHTML = `${getCartIcon()}<span class="cart-nav-count"${countId}>${count}</span>`;
            link.setAttribute('aria-label', count ? `Einkaufswagen, ${count} Artikel` : 'Einkaufswagen');
            link.setAttribute('title', count ? `Einkaufswagen (${count})` : 'Einkaufswagen');
            link.classList.toggle('has-items', count > 0);
        });
    }

    window.updateCartNavigation = updateCartNavigation;
    document.addEventListener('DOMContentLoaded', updateCartNavigation);
    window.addEventListener('storage', updateCartNavigation);
})();
