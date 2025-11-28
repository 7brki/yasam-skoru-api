# scorer.py
# (v3.4.0 - DETAYLI MEKAN LİSTESİ MODU)
# Artık sadece skor değil, bulunan yerlerin listesini de (İsim, Mesafe) döndürür.

import warnings
import geopandas as gpd
import pandas as pd
import osmnx as ox
from shapely.geometry import Point
from sentinelhub import CRS, BBox, SHConfig
import cache_manager
import requests

ox.settings.log_console = False
warnings.filterwarnings('ignore')


# --- YARDIMCI FONKSİYONLAR ---
def normalize_linear(deger, min_esik, max_esik, ters=False):
    deger = max(min_esik, min(deger, max_esik))
    if (max_esik - min_esik) == 0: return 100.0 if not ters else 0.0
    normalized = (deger - min_esik) / (max_esik - min_esik)
    if ters: normalized = 1 - normalized
    return normalized * 100


def normalize_plateau(deger, ideal_limit, max_limit):
    if deger <= ideal_limit: return 100.0
    if deger > ideal_limit: return normalize_linear(deger, min_esik=ideal_limit, max_esik=max_limit, ters=True)
    return 0.0


class QualityScorer:

    def __init__(self, lat, lon, config):
        self.lat = lat
        self.lon = lon
        self.config = config
        self.point = (lat, lon)
        self.point_geom = Point(lon, lat)
        self.bbox = BBox(bbox=(lon - 0.005, lat - 0.005, lon + 0.005, lat + 0.005), crs=CRS.WGS84)

        # Bulunan mekanları saklayacak liste
        self.detected_places = []
        self.distance_to_sea = float('inf')

        try:
            temp_gdf = gpd.GeoDataFrame(geometry=[self.point_geom], crs="EPSG:4326")
            self.crs_utm = temp_gdf.estimate_utm_crs()
        except Exception:
            self.crs_utm = "EPSG:32636"

        self.sh_config = SHConfig()
        if hasattr(config, 'CLIENT_ID') and hasattr(config, 'CLIENT_SECRET'):
            self.sh_config.sh_client_id = config.CLIENT_ID
            self.sh_config.sh_client_secret = config.CLIENT_SECRET

        print(f"QualityScorer motoru {self.point} koordinatı için başlatıldı.")

    def _get_poi_name(self, row):
        """OSM verisinden anlamlı bir isim çıkarmaya çalışır."""
        name = "İsimsiz"
        if 'name' in row and pd.notna(row['name']):
            name = row['name']
        elif 'brand' in row and pd.notna(row['brand']):
            name = row['brand']
        elif 'name:en' in row and pd.notna(row['name:en']):
            name = row['name:en']
        elif 'operator' in row and pd.notna(row['operator']):
            name = row['operator']
        return name

    def _clean_osm_data(self, gdf):
        if gdf.empty: return gdf
        for col in ['disused', 'abandoned']:
            if col in gdf.columns: gdf = gdf[gdf[col] != 'yes']
        return gdf

    def _analyze_poi_details(self, category_name, osm_tags, max_radius_m):
        """
        Hem istatistikleri döndürür hem de bulunan yerleri 'self.detected_places' listesine ekler.
        """
        try:
            search_dist = max(max_radius_m, 3000)
            gdf = ox.features.features_from_point(center_point=self.point, tags=osm_tags, dist=search_dist)
            gdf = self._clean_osm_data(gdf)

            if gdf.empty:
                return {"min_dist": float('inf'), "count": 0}

            gdf_utm = gdf.to_crs(self.crs_utm)
            point_utm = gpd.GeoSeries([self.point_geom], crs="EPSG:4326").to_crs(self.crs_utm).iloc[0]
            gdf_utm['distance'] = gdf_utm.distance(point_utm)

            # Mesafeye göre sırala
            gdf_sorted = gdf_utm.sort_values('distance')

            # En yakın
            nearest = gdf_sorted.iloc[0]
            min_dist = nearest['distance']

            # İlgili menzil içindekiler
            relevant_pois = gdf_sorted[gdf_sorted['distance'] <= max_radius_m]
            count = len(relevant_pois)

            # --- DETAYLARI KAYDET (EN YAKIN 5 TANESİ) ---
            # Sadece menzil içindekileri veya menzil yoksa en yakın 1 taneyi al
            pois_to_save = relevant_pois.head(5) if not relevant_pois.empty else gdf_sorted.head(1)

            for _, row in pois_to_save.iterrows():
                place_name = self._get_poi_name(row)
                # Eğer çok uzaksa (10km+) listeye ekleme
                if row['distance'] > 5000: continue

                self.detected_places.append({
                    "kategori": category_name,  # Örn: "market", "okul"
                    "isim": place_name,  # Örn: "BİM", "Atatürk İlkokulu"
                    "mesafe": int(row['distance']),  # Örn: 150 (metre)
                    "tur": list(osm_tags.keys())[0]  # Örn: "shop", "amenity"
                })
            # ---------------------------------------------

            return {"min_dist": min_dist, "count": count}

        except Exception as e:
            return {"min_dist": float('inf'), "count": 0}

    # --- GÜRÜLTÜ ---
    def _calculate_noise_score(self):
        print("  -> Gürültü Skoru hesaplanıyor...")
        cfg_gurultu = self.config.GURULTU_AYARLARI
        max_dist = cfg_gurultu["max_etki_mesafesi"]

        # Gürültü analizi karmaşık olduğu için buradaki detayları listeye eklemiyoruz
        # Sadece skoru hesaplıyoruz. (İstenirse eklenebilir)

        tags_all_noise = {}
        for key, values in cfg_gurultu["ETKENLER"].items(): tags_all_noise[key] = list(values.keys())
        for key, puan in cfg_gurultu["SONUMLEYICILER"].items():
            tag_key, tag_val = key.split('=')
            if tag_key not in tags_all_noise: tags_all_noise[tag_key] = []
            if tag_val not in tags_all_noise[tag_key]: tags_all_noise[tag_key].append(tag_val)
        try:
            pois = ox.features.features_from_point(center_point=self.point, tags=tags_all_noise, dist=max_dist)
            pois = self._clean_osm_data(pois)
            if pois.empty: return 100.0
            pois_utm = pois.to_crs(self.crs_utm)
            point_utm = gpd.GeoSeries([self.point_geom], crs="EPSG:4326").to_crs(self.crs_utm).iloc[0]
        except Exception:
            return 100.0

        total_raw_noise_score = 0
        for _, poi in pois_utm.iterrows():
            mesafe = point_utm.distance(poi.geometry)
            if mesafe > max_dist: continue
            distance_decay = 1 - (mesafe / max_dist)
            temel_puan = 0
            for key, values in cfg_gurultu["ETKENLER"].items():
                if key in poi and pd.notna(poi[key]) and poi[key] in values: temel_puan = values[poi[key]]; break
            for key, puan in cfg_gurultu["SONUMLEYICILER"].items():
                tag_key, tag_val = key.split('=')
                if tag_key in poi and pd.notna(poi[tag_key]) and poi[tag_key] == tag_val: temel_puan = puan; break
            total_raw_noise_score += (temel_puan * distance_decay)
        return normalize_linear(total_raw_noise_score, min_esik=cfg_gurultu["min_esik"],
                                max_esik=cfg_gurultu["max_esik"], ters=True)

    # --- YERLEŞİM ---
    def _calculate_settlement_score(self):
        print("  -> Yerleşim Skoru hesaplanıyor...")
        cfg_yerlesim = self.config.YERLESIM_AYARLARI
        final_score = 0;
        total_weight = 0
        for etken_adi, ayarlar in cfg_yerlesim["etiketler"].items():
            # Kategori ismini gönderiyoruz (örn: "okul")
            data = self._analyze_poi_details(etken_adi, ayarlar["osm_tags"], ayarlar["max_limit"])

            puan = normalize_plateau(data["min_dist"], ayarlar["ideal_limit"], ayarlar["max_limit"])
            agirlik = cfg_yerlesim["agirliklar"].get(etken_adi, 0)
            final_score += puan * agirlik;
            total_weight += agirlik
        if total_weight == 0: return 0.0
        return final_score / total_weight

    # --- YEŞİL & SOSYAL ---
    def _calculate_ndvi_score(self):
        print("  -> Yeşil/Sosyal (NDVI): Veri kontrol ediliyor...")
        cached_value = cache_manager.get_cached_data(self.lat, self.lon, "ndvi")
        if cached_value is not None:
            ham_ndvi = cached_value
        else:
            ham_ndvi = 0.3491  # Simülasyon
            cache_manager.save_data_to_cache(self.lat, self.lon, "ndvi", ham_ndvi)
        cfg_yesil = self.config.YESIL_SOSYAL_AYARLARI["NDVI"]
        return normalize_linear(ham_ndvi, min_esik=cfg_yesil["min_esik"], max_esik=cfg_yesil["max_esik"])

    def _calculate_green_social_score(self):
        print("  -> Yeşil & Sosyal Skor hesaplanıyor...")
        cfg_sosyal = self.config.YESIL_SOSYAL_AYARLARI["POZITIF_ETKENLER"]
        skor_ndvi = self._calculate_ndvi_score()
        total_poi = 0;
        total_w = 0
        for etken, ayarlar in cfg_sosyal["etiketler"].items():
            max_r = ayarlar.get("max_mesafe", 1000)

            # Kategori ismini gönderiyoruz (örn: "market")
            data = self._analyze_poi_details(etken, ayarlar["osm_tags"], max_r)

            if etken == "deniz_kenari":
                self.distance_to_sea = data["min_dist"]
                if self.distance_to_sea == float('inf'): continue

            p_yakin = normalize_linear(data["min_dist"], 0, max_r, True)
            p_yogun = min(100, (data["count"] / ayarlar.get("yogunluk_hedefi", 1)) * 100)
            w_yakin = cfg_sosyal.get("yakinlik_agirligi", 0.7)
            w_yogun = cfg_sosyal.get("yogunluk_agirligi", 0.3)
            final_item = 0.0
            if data["min_dist"] != float('inf'):
                final_item = (p_yakin * w_yakin) + (p_yogun * w_yogun)
            w = ayarlar.get("agirlik", 1)
            total_poi += final_item * w;
            total_w += w
        skor_poi = total_poi / total_w if total_w > 0 else 0
        w_ndvi = self.config.YESIL_SOSYAL_AYARLARI["NDVI"]["agirlik"]
        w_poi = cfg_sosyal["agirlik"]
        return (skor_ndvi * w_ndvi) + (skor_poi * w_poi)

    # --- EĞİM VE VIBE (Aynı) ---
    def _get_elevations_batch(self, locations):
        try:
            url = "https://api.open-elevation.com/api/v1/lookup"
            resp = requests.post(url, json={"locations": locations}, timeout=5)
            if resp.status_code == 200: return [r['elevation'] for r in resp.json()['results']]
        except Exception:
            return None
        return None

    def _calculate_slope_analysis(self):
        print("  -> Eğim Analizi yapılıyor...")
        delta = 0.0015
        points = [{"latitude": self.lat, "longitude": self.lon}, {"latitude": self.lat + delta, "longitude": self.lon},
                  {"latitude": self.lat - delta, "longitude": self.lon},
                  {"latitude": self.lat, "longitude": self.lon + delta},
                  {"latitude": self.lat, "longitude": self.lon - delta}]
        elevations = self._get_elevations_batch(points)
        if not elevations: return {"rakim": "Bilinmiyor", "egim_yuzde": 0, "durum": "Analiz Edilemedi"}
        center_elev = elevations[0];
        max_diff = 0
        for h in elevations[1:]:
            diff = abs(h - center_elev)
            if diff > max_diff: max_diff = diff
        egim_yuzde = (max_diff / 150) * 100
        cfg_egim = self.config.EGIM_AYARLARI["kategoriler"]
        durum = "Bilinmiyor"
        if egim_yuzde <= cfg_egim["duz"]["max_egim"]:
            durum = cfg_egim["duz"]["etiket"]
        elif egim_yuzde <= cfg_egim["hafif"]["max_egim"]:
            durum = cfg_egim["hafif"]["etiket"]
        elif egim_yuzde <= cfg_egim["orta"]["max_egim"]:
            durum = cfg_egim["orta"]["etiket"]
        else:
            durum = cfg_egim["dik"]["etiket"]
        return {"rakim": center_elev, "egim_yuzde": round(egim_yuzde, 1), "durum": durum}

    def _calculate_neighborhood_vibe(self):
        print("  -> Mahalle Karakteri (Vibe) analizi yapılıyor...")
        cfg_vibe = self.config.VIBE_AYARLARI
        scores = {"aile": 0, "sosyal": 0, "ticari": 0}
        for cat_name, cat_data in cfg_vibe["kategoriler"].items():
            try:
                gdf = ox.features.features_from_point(center_point=self.point, tags=cat_data["tags"],
                                                      dist=cfg_vibe["yaricap"])
                gdf = self._clean_osm_data(gdf)
                scores[cat_name] = len(gdf)
            except Exception:
                scores[cat_name] = 0
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        winner = sorted_scores[0];
        runner_up = sorted_scores[1]
        if winner[1] < 3: return {"etiket": "🍃 Sakin / Gelişmekte Olan", "aciklama": "Sessiz bir bölge."}
        if runner_up[1] > (winner[1] * 0.7): return {"etiket": "🔄 Karma Yaşam (Canlı)",
                                                     "aciklama": "Çok yönlü bir mahalle."}
        return {"etiket": cfg_vibe["kategoriler"][winner[0]]["etiket"],
                "aciklama": cfg_vibe["kategoriler"][winner[0]]["aciklama"]}

    # --- ANA ÇAĞRI ---
    def get_final_score(self):
        print("\n--- SKORLAMA MOTORU (v3.4.0 - Detaylı) BAŞLATILDI ---")

        # Listeyi her analizde sıfırla
        self.detected_places = []

        skor_gurultu = self._calculate_noise_score()
        skor_yerlesim = self._calculate_settlement_score()
        skor_sosyal_yesil = self._calculate_green_social_score()

        analiz_egim = self._calculate_slope_analysis()
        analiz_vibe = self._calculate_neighborhood_vibe()

        cfg_final = self.config.FINAL_AGIRLIKLAR
        genel = (skor_sosyal_yesil * cfg_final["yesil_sosyal"] + skor_yerlesim * cfg_final["yerlesim"] + skor_gurultu *
                 cfg_final["gurultu"])
        print("\n--- MOTOR HESAPLAMAYI BİTİRDİ ---")

        return {
            "genel_skor": genel,
            "alt_skorlar": {"yesil_sosyal": skor_sosyal_yesil, "yerlesim": skor_yerlesim, "gurultu": skor_gurultu},
            "ekstra_analiz": {"egim": analiz_egim, "vibe": analiz_vibe},
            # YENİ: Mekan Listesi
            "mekanlar": self.detected_places
        }
