# config.py
# Emlak Değerleme Motoru - Gelişmiş Yapılandırma (v3.2 Final)
# Tüm ayarlar Türkiye şehir standartlarına ve emlak literatürüne göre kalibre edilmiştir.

import os

# --- GÜVENLİK ---
# Kodun içine şifre yazmıyoruz! Sunucudan (Environment Variable) okuyacağız.
# Eğer kendi bilgisayarında test ediyorsan, bu değişkenleri manuel olarak atamalısın.
CLIENT_ID = os.environ.get("SH_CLIENT_ID")
CLIENT_SECRET = os.environ.get("SH_CLIENT_SECRET")

# ---------------------------------------------------------------------
# --- BÖLÜM 1: YEŞİL & SOSYAL SKOR (YAKINLIK + YOĞUNLUK) ---
# ---------------------------------------------------------------------
YESIL_SOSYAL_AYARLARI = {
    "NDVI": {
        "agirlik": 0.3,
        "min_esik": 0.15,
        "max_esik": 0.55
    },
    "POZITIF_ETKENLER": {
        "agirlik": 0.7,
        "yakinlik_agirligi": 0.7,
        "yogunluk_agirligi": 0.3,
        "etiketler": {
            "deniz_kenari": {
                "agirlik": 4, "max_mesafe": 2000, "yogunluk_hedefi": 1,
                "osm_tags": {'natural': ['coastline', 'beach', 'bay']} # 'water' çıkarıldı (Göl/Havuz hatası önlendi)
            },
            "market": {
                "agirlik": 3, "max_mesafe": 800, "yogunluk_hedefi": 5,
                "osm_tags": {'shop': ['supermarket', 'convenience', 'mall', 'greengrocer']}
            },
            "park": {
                "agirlik": 2, "max_mesafe": 800, "yogunluk_hedefi": 3,
                "osm_tags": {'leisure': ['park', 'garden', 'playground'], 'natural': ['wood']}
            },
            "ulasim": {
                "agirlik": 1, "max_mesafe": 400, "yogunluk_hedefi": 4,
                "osm_tags": {'highway': ['bus_stop'], 'public_transport': ['stop_position', 'platform'], 'railway': ['tram_stop']}
            },
            "sosyal_tesis": {
                "agirlik": 2, "max_mesafe": 600, "yogunluk_hedefi": 10,
                "osm_tags": {'amenity': ['cinema', 'theatre', 'library', 'cafe', 'restaurant', 'bar', 'pub'], 'leisure': ['fitness_centre', 'sports_centre', 'swimming_pool']}
            }
        }
    }
}

# ---------------------------------------------------------------------
# --- BÖLÜM 2: YERLEŞİM SKORU (PLATO MODELİ) ---
# ---------------------------------------------------------------------
YERLESIM_AYARLARI = {
    "agirliklar": { "okul": 0.35, "saglik": 0.30, "ibadethane": 0.20, "guvenlik": 0.15 },
    "etiketler": {
        "okul": { "osm_tags": {'amenity': ['school', 'university', 'college', 'kindergarten']}, "ideal_limit": 400, "max_limit": 1500 },
        "saglik": { "osm_tags": {'amenity': ['hospital', 'clinic', 'pharmacy']}, "ideal_limit": 400, "max_limit": 2000 },
        "ibadethane": { "osm_tags": {'amenity': ['place_of_worship']}, "ideal_limit": 300, "max_limit": 800 },
        "guvenlik": { "osm_tags": {'amenity': ['police', 'fire_station']}, "ideal_limit": 1000, "max_limit": 3000 }
    }
}

# ---------------------------------------------------------------------
# --- BÖLÜM 3: GÜRÜLTÜ SKORU (NEGATİFLER) ---
# ---------------------------------------------------------------------
GURULTU_AYARLARI = {
    "max_etki_mesafesi": 500, "min_esik": 200, "max_esik": 5000,
    "SONUMLEYICILER": { 'leisure=park': -50, 'natural=wood': -100, 'natural=water': -30 },
    "ETKENLER": {
        "highway": { "motorway": 100, "primary": 80, "trunk": 80, "secondary": 50, "tertiary": 20 },
        "aeroway": { "aerodrome": 2000, "runway": 1000 },
        "amenity": { "nightclub": 150, "bar": 40, "pub": 40, "music_venue": 60, "cafe": 5, "restaurant": 10, "fast_food": 15, "school": 20, "place_of_worship": 15, "hospital": 50, "fire_station": 60 },
        "leisure": { "stadium": 100, "water_park": 40 },
        "landuse": { "industrial": 80, "construction": 60, "railway": 70 },
        "shop": { "supermarket": 5, "mall": 30, "bakery": 5, "optician": 0 }
    }
}

# ---------------------------------------------------------------------
# --- BÖLÜM 4: EĞİM VE MANZARA ANALİZİ ---
# ---------------------------------------------------------------------
MANZARA_AYARLARI = {
    "yukseklik_bonusu": { "min_rakim": 20, "iyi_rakim": 60 }
}

EGIM_AYARLARI = {
    "kategoriler": {
        "duz": { "max_egim": 3, "etiket": "Düzayak (Mükemmel)", "puan": 100 },
        "hafif": { "max_egim": 8, "etiket": "Hafif Eğimli", "puan": 85 },
        "orta": { "max_egim": 15, "etiket": "Yokuş", "puan": 60 },
        "dik": { "max_egim": 100, "etiket": "Dik Yokuş", "puan": 30 }
    }
}

# ---------------------------------------------------------------------
# --- BÖLÜM 5: MAHALLE KARAKTERİ (VIBE) ---
# ---------------------------------------------------------------------
VIBE_AYARLARI = {
    "yaricap": 500,
    "kategoriler": {
        "aile": { "etiket": "👨‍👩‍👧‍👦 Aile Dostu & Yerleşim", "aciklama": "Okul, park ve marketlerin yoğun olduğu, aile yaşamına uygun bölge.", "tags": {'amenity': ['school', 'kindergarten', 'place_of_worship', 'pharmacy', 'clinic'], 'leisure': ['park', 'playground'], 'shop': ['supermarket', 'greengrocer', 'bakery']} },
        "sosyal": { "etiket": "🎉 Sosyal & Hareketli", "aciklama": "Kafe, restoran ve eğlence mekanlarının yoğun olduğu, genç ve dinamik bölge.", "tags": {'amenity': ['bar', 'cafe', 'pub', 'nightclub', 'restaurant', 'university', 'theatre', 'cinema'], 'leisure': ['fitness_centre']} },
        "ticari": { "etiket": "💼 Ticari & İş Merkezi", "aciklama": "İş yerleri, bankalar ve otellerin bulunduğu, gündüz hareketli bölge.", "tags": {'amenity': ['bank', 'atm', 'post_office'], 'building': ['office', 'commercial', 'hotel'], 'landuse': ['commercial', 'retail'], 'shop': ['mall', 'department_store', 'electronics']} }
    }
}

# ---------------------------------------------------------------------
# --- BÖLÜM 6: FİNAL SKOR AĞIRLIKLARI ---
# ---------------------------------------------------------------------
FINAL_AGIRLIKLAR = {
    "yesil_sosyal": 0.35,
    "yerlesim": 0.45,
    "gurultu": 0.20
}