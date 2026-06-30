const GeberitDatabase = (() => {
    const SUPABASE_URL = 'https://dfqezgjgvevietewqrci.supabase.co';
    const SUPABASE_PUBLISHABLE_KEY = 'sb_publishable_R__QyYodPo3dnVb9RJqqkg_UTAZXqyP';
    const PRODUCTS_TABLE = 'products';
    const PRODUCT_CLICKS_TABLE = 'product_clicks';

    function isConfigured() {
        return !SUPABASE_URL.includes('HIER_DEINE')
            && !SUPABASE_PUBLISHABLE_KEY.includes('HIER_DEINEN');
    }

    function normalizeProduct(row) {
        return {
            id: row.id,
            name: row.name,
            description: row.description || row.material || '',
            price: row.price || '',
            articleNumber: row.article_number || '',
            image: row.image_url || '',
            material: row.material || '',
            category: row.category || 'wc'
        };
    }

    async function getVisitorIp() {
        try {
            const response = await fetch('https://api.ipify.org?format=json');
            if (!response.ok) {
                return '';
            }

            const data = await response.json();
            return data.ip || '';
        } catch (error) {
            console.warn('IP-Adresse konnte nicht geladen werden.', error);
            return '';
        }
    }

    function getHeaders(extraHeaders = {}) {
        return {
            apikey: SUPABASE_PUBLISHABLE_KEY,
            Authorization: `Bearer ${SUPABASE_PUBLISHABLE_KEY}`,
            ...extraHeaders
        };
    }

    async function loadProducts() {
        if (!isConfigured()) {
            console.info('Supabase ist noch nicht konfiguriert. Lokale Produktdaten werden benutzt.');
            return null;
        }

        const endpoint = `${SUPABASE_URL}/rest/v1/${PRODUCTS_TABLE}?select=*&active=eq.true&order=sort_order.asc`;
        const response = await fetch(endpoint, {
            headers: getHeaders()
        });

        if (!response.ok) {
            throw new Error(`Supabase Fehler: ${response.status} ${response.statusText}`);
        }

        const rows = await response.json();
        return rows.reduce((groups, row) => {
            const product = normalizeProduct(row);
            groups[product.category] = groups[product.category] || [];
            groups[product.category].push(product);
            return groups;
        }, {});
    }

    async function saveProductClick(clickData) {
        if (!isConfigured()) {
            return false;
        }

        const ipAddress = await getVisitorIp();

        const endpoint = `${SUPABASE_URL}/rest/v1/${PRODUCT_CLICKS_TABLE}`;
        const response = await fetch(endpoint, {
            method: 'POST',
            headers: getHeaders({
                'Content-Type': 'application/json',
                Prefer: 'return=minimal'
            }),
            body: JSON.stringify({
                ...clickData,
                ip_address: ipAddress || null
            })
        });

        if (!response.ok) {
            throw new Error(`Supabase Klickspeicherung Fehler: ${response.status} ${response.statusText}`);
        }

        return true;
    }

    return {
        loadProducts,
        saveProductClick
    };
})();
