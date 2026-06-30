delete from products
where name in (
    'Geberit ONE Moebelwaschtisch',
    'Geberit Olona Design-Duschflaeche'
);

with duplicates as (
    select
        ctid,
        row_number() over (partition by name order by id) as row_number
    from products
)
delete from products
where ctid in (
    select ctid
    from duplicates
    where row_number > 1
);

create unique index if not exists products_name_unique
on products (name);

insert into products (name, category, description, price, article_number, image_url, material, active, sort_order)
values
('Geberit Sigma20 Betätigungsplatte für 2-Mengen-Spülung', 'wc', 'Saubere und moderne Bedienung für eine praktische 2-Mengen-Spülung mit ansprechender Optik im WC-Bereich.', 'ab € 135', 'ART-115882161', 'https://www.baedermaxx.at/media/image/4f/e6/82/Geberit-Sigma20-Bet-tigungsplatte-f-r-2-Mengen-Sp-lung-schwarzchrom-hochglanzschwarz_1_600x600@2x.webp', null, true, 10),
('Geberit Delta50 Betätigungsplatte für 2-Mengen-Spülung', 'wc', 'Komfortable und einfache Bedienung für eine moderne Spülung mit zeitgemäßem Design.', 'ab € 61', 'ART-115135465', 'https://www.baedermaxx.at/media/image/36/26/82/Geberit-Delta50-Bet-tigungsplatte-f-r-2-Mengen-Sp-lung-mattchrom_1_600x600@2x.webp', null, true, 20),
('Geberit AquaClean Mera', 'wc', 'Eine hochwertige Dusch-WC-Lösung mit komfortabler Technik und angenehmer Nutzung im Alltag.', 'ab € 3.660', 'ART-146210111', 'https://www.baedermaxx.at/media/image/b4/1f/60/Geberit-AquaClean-Mera-Comfort-Wand-Dusch-WC-Komplettanlage_600x600@2x.webp', 'Sanitärkeramik', true, 30),
('Geberit Monolith Sanitärmodul für Wand-WC', 'wc', 'Ein modernes Sanitärmodul für Wand-WCs mit sauberer Optik und gut durchdachter Installation.', 'ab € 1150', 'ART-131031SI5', 'https://www.baedermaxx.at/media/image/2a/71/g0/Geberit-Monolith-Sanit-rmodul-f-r-Wand-WC-114cm-131031SI5_600x600@2x.webp', null, true, 40),
('Geberit Renova WC-Sitz mit Sitzring für Kinder, mit Absenkautomatik', 'wc', 'Praktischer WC-Sitz mit angenehmer Nutzung, einfacher Bedienung und kindersicherem Komfort.', 'ab € 209', 'ART-500981011', 'https://www.baedermaxx.at/media/image/8b/75/dc/Geberit-Renova-WC-Sitz-mit-Sitzring-f-r-Kinder-mit-Absenkautomatik-weiss-500981011_600x600@2x.webp', null, true, 50),
('Geberit Duofix Montageelement für Wand-WC mit UP-Spülkasten Sigma UP320', 'wc', 'Robuste Montage für Wand-WCs mit durchdachtem Spülkastensystem und zuverlässiger Funktion.', 'ab € 325', 'ART-111311006', 'https://www.baedermaxx.at/media/image/bd/f2/da/Geberit-Duofix-Montageelement-f-r-Wand-WC-mit-UP-Sp-lkasten-UP320-BH-112cm-111-311-00-5_1_600x600@2x.webp', null, true, 60),
('Geberit ONE Möbelwaschtisch', 'waschbecken', 'Moderner Waschtisch für klare Badezimmergestaltung.', '383,28€', null, 'https://www.obadis.com/media/catalog/product/cache/207e23213cf636ccdef205098cf3c8a3/k/a/kataloge_geberit_vgabild_geb_w_2226616_20210914_112611.jpeg___/Geberit-One-Moebel-Waschtisch-505002001-60-cm,-Hahnloch-mittig,-ohne-Ueberlauf,-weiss-KeraTect-Blende-weiss.jpeg', 'Sanitärkeramik KeraTect', true, 70),
('Geberit iCon Light Waschtisch', 'waschbecken', 'Hochwertiger Waschtisch mit zeitloser Form.', '369,54€', null, 'https://www.obadis.com/media/catalog/product/cache/207e23213cf636ccdef205098cf3c8a3/k/a/kataloge_geberit_vgabild_geb_w_1889931_20200923_165731.jpeg___/Geberit-iCon-light-Waschtisch-501837001-120x48cm,-Hahnloch-links-rechts,-mit-Ueberlauf,-weiss.jpeg', 'Feuerton Spezialglasur', true, 80),
('Geberit VariForm Aufsatzwaschbecken', 'waschbecken', 'Aufsatzwaschbecken in ovaler Form für moderne Badezimmer.', '209,65€', null, 'https://www.obadis.com/media/catalog/product/cache/207e23213cf636ccdef205098cf3c8a3/k/a/kataloge_geberit_vgabild_geb_w_508719_20170925_152956.jpeg___/Geberit-VariForm-Aufsatzwaschtisch-500779002-55x40cm,-ohne-Hahnloch,-Ueberlauf,-rechteckig,-weiss-KeraTect.jpeg', 'Sanitärkeramik (Oval)', true, 90),
('Geberit Acanto Kompaktwaschtisch', 'waschbecken', 'Kompakter Waschtisch mit Ablagefläche.', '250,53€', null, 'https://www.obadis.com/media/catalog/product/cache/207e23213cf636ccdef205098cf3c8a3/k/a/kataloge_geberit_vgabild_geb_w_522616_20200619_124631.jpeg___/Geberit-Acanto-Compact-Waschtisch-500632012-weiss,-mit-Ueberlauf,-75-x-42-cm.jpeg', 'Sanitärkeramik mit Ablage', true, 100),
('Geberit Renova Plan Waschtisch', 'waschbecken', 'Klassischer Waschtisch für funktionale Badezimmer.', '231,03€', null, 'https://www.obadis.com/media/catalog/product/cache/207e23213cf636ccdef205098cf3c8a3/k/a/kataloge_geberit_vgabild_geb_w_1947096_20201020_093820.jpeg___/Geberit-One-Waschtisch-Platte-505314001-105-x-3-x-47-cm,-weiss-lackiert-hochglaenzend,-Ausschnitt-rechts.jpeg', 'Klassische Sanitärkeramik', true, 110),
('Geberit Smyle Waschtisch eckig', 'waschbecken', 'Eckiger Waschtisch mit klarer Linienführung.', '268,57€', null, 'https://www.obadis.com/media/catalog/product/cache/207e23213cf636ccdef205098cf3c8a3/k/a/kataloge_geberit_vgabild_geb_w_387294_20180920_102239.jpeg___/Geberit-Smyle-Square-Waschtisch-500253011-weiss,-120x48cm,-mit-Hahnloch-und-Ueberlauf.jpeg', 'Sanitärkeramik', true, 120),
('Geberit AquaClean Mera Luxus-Dusch-WC', 'wc', 'Luxus-Dusch-WC mit hochwertiger Technik.', '3.805,32€', null, 'https://www.obadis.com/media/catalog/product/cache/207e23213cf636ccdef205098cf3c8a3/k/a/kataloge_geberit__bildfarbe_645b5caad7830aaf9d7ee7257678980c_screenshot_2026-01-22_083051.png___/Geberit-AquaClean-Alba-Dusch-WC-spuelrandlos-146350011-weiss-KeraTect,-Komplettanlage.png', 'Sanitärkeramik & High-End ABS', true, 130),
('Geberit AquaClean Tuma Comfort', 'wc', 'Dusch-WC mit komfortabler Ausstattung.', '1.924,36€', null, 'https://images.emero.de/products/ge/568x568/geberit-aquaclean-tuma-wand-dusch-wc-comfort-mit-wc-sitz-l-55-b-35-cm-mit-schmutzabweisender-oberflaeche-weiss--ge-146290111_7a.jpg', 'Sanitärkeramik / KeraTect', true, 140),
('Geberit iCon Wand-WC Rimfree', 'wc', 'Spülrandloses Wand-WC mit moderner Optik.', '372,15€', null, 'https://www.obadis.com/media/catalog/product/cache/207e23213cf636ccdef205098cf3c8a3/k/a/kataloge_geberit_milieu_gemi_cs1038062228.jpeg___/Geberit-iCon-WC-Set-Wand-Tiefspuel-WC-501664008-36x53cm,--geschlossene-Form,-rimfree,-mit-WC-Sitz,-weiss-KeraTect.jpeg', 'Spülrandlose Keramik', true, 150),
('Geberit Acanto Wand-WC TurboFlush', 'wc', 'Wand-WC mit TurboFlush-Technik.', '389,00€', null, 'https://cdn.idealo.com/folder/Product/202386/6/202386670/s1_produktbild_gross/geberit-acanto-set-wand-wc-502774001.jpg', 'Sanitärkeramik geschlossen', true, 160),
('Geberit ONE Premium Wand-WC', 'wc', 'Premium-Wand-WC für hochwertige Badezimmer.', '1.589,36€', null, 'https://www.baedermaxx.at/media/image/c2/83/16/Geberit_ONE_WC_Detail_1.jpg', 'Premium-Keramik', true, 170),
('Geberit Renova Wand-WC', 'wc', 'Klassisches Wand-WC für moderne Sanitärräume.', '391,56€', null, 'https://img.reuter.de/products/ge/ge-renovaplan-wand-milieu_0.jpg', 'Klassische Sanitärkeramik', true, 180),
('Geberit CleanLine Edelstahl-Duschrinne', 'dusche', 'Bodenebene Duschrinne mit sauberer Edelstahloptik.', '363,32€', null, 'https://www.obadis.com/media/catalog/product/cache/207e23213cf636ccdef205098cf3c8a3/k/a/kataloge_geberit_milieu_gemi_cs29337358.jpeg___/Geberit-CleanLine-50-Duschrinne-154448KS2-30-110-x-3-cm,-Edelstahl-gebuerstet,-bodeneben.jpeg', 'Edelstahl matt / poliert', true, 190),
('Geberit Olona Design-Duschfläche', 'dusche', 'Flache Duschfläche für moderne Badezimmer.', '631,59€', null, 'https://www.obadis.com/media/catalog/product/cache/207e23213cf636ccdef205098cf3c8a3/k/a/kataloge_geberit_vgabild_geb_w_4077617_20240426_065545.jpeg___/Geberit-Olona-Rechteckduschwanne-550919001-weiss-matt,-140-x-90-x-4-cm.jpeg', 'Stein-Harz-Mineralwerkstoff', true, 200),
('Geberit Setaplano Duschfläche', 'dusche', 'Porenfreie Duschfläche aus Mineralwerkstoff.', '216,33€', null, 'https://www.obadis.com/media/catalog/product/cache/207e23213cf636ccdef205098cf3c8a3/k/a/kataloge_geberit_vgabild_geb_w_1583848_20200928_144329.jpeg___/Geberit-Setaplano-Duschbodenablauf-154055001-o-50-mm,-fuer-Estrichhoehe-am-Einlauf-114-215mm.jpeg', 'Mineralwerkstoff porenfrei', true, 210),
('Geberit Wandablauf für Dusche', 'dusche', 'Wandablauf für bodenebene Duschen.', '307,44€', null, 'https://www.obadis.com/media/catalog/product/cache/207e23213cf636ccdef205098cf3c8a3/k/a/kataloge_geberit_vgabild_geb_w_145284_20170925_163001.jpeg___/Geberit-Kombifix-Element-fuer-Dusche-457534001-mit-Wandablauf,-d50.jpeg', 'Edelstahl / Kunststoff', true, 220),
('Geberit Wandablauf Duofix Dusch-Element', 'dusche', 'Duofix Dusch-Element mit Wandablauf.', '271,93€', null, 'https://www.obadis.com/media/catalog/product/cache/207e23213cf636ccdef205098cf3c8a3/k/a/kataloge_geberit_vgabild_geb_w_4257439_20240626_111341.jpeg___/Geberit-Duofix-Dusch-Element-111591002-BH-50-cm,-mit-Wandablauf,-d=-50mm.jpeg', 'Stahlrahmen / EPS-Träger', true, 230)
on conflict (name) do update set
    category = excluded.category,
    description = excluded.description,
    price = excluded.price,
    article_number = excluded.article_number,
    image_url = excluded.image_url,
    material = excluded.material,
    active = excluded.active,
    sort_order = excluded.sort_order;
