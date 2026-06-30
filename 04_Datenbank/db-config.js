const GeberitDatabase = (() => {
    const SUPABASE_URL = 'HIER_DEINE_SUPABASE_URL_EINFUEGEN';
    const SUPABASE_ANON_KEY = 'HIER_DEINEN_SUPABASE_ANON_KEY_EINFUEGEN';
    const PRODUCTS_TABLE = 'products';

    function isConfigured() {
        return !SUPABASE_URL.includes('HIER_DEINE')
            && !SUPABASE_ANON_KEY.includes('HIER_DEINEN');
    }

    function normalizeProduct(row) {
        return {
            name: row.name,
            description: row.description || row.material || '',
            price: row.price || '',
            articleNumber: row.article_number || '',
            image: row.image_url || '',
            material: row.material || '',
            category: row.category || 'wc'
        };
    }

    async function loadProducts() {
        if (!isConfigured()) {
            console.info('Supabase ist noch nicht konfiguriert. Lokale Produktdaten werden benutzt.');
            return null;
        }

        const endpoint = `${SUPABASE_URL}/rest/v1/${PRODUCTS_TABLE}?select=*&active=eq.true&order=sort_order.asc`;
        const response = await fetch(endpoint, {
            headers: {
                apikey: SUPABASE_ANON_KEY,
                Authorization: `Bearer ${SUPABASE_ANON_KEY}`
            }
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

    return {
        loadProducts
    };
})();
