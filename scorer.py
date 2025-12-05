# scorer.py (v4.2.0 - HIZLI VERSİYON)
import warnings
import geopandas as gpd
import pandas as pd
import osmnx as ox
from shapely.geometry import Point
from sentinelhub import CRS, BBox, SHConfig
import cache_manager
import requests
import concurrent.futures

ox.settings.log_console = False
warnings.filterwarnings('ignore')

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
        self.bbox = BBox(bbox=(lon-0.005, lat-0.005, lon+0.005, lat+0.005), crs=CRS.WGS84)
        self.detected_places = []
        self.distance_to_sea = float('inf')
        self.score_details = {}  # YENI: Detayları sakla
        
        try:
            temp_gdf = gpd.GeoDataFrame(geometry=[self.point_geom], crs="EPSG:4326")
            self.crs_utm = temp_gdf.estimate_utm_crs()
        except Exception:
            self.crs_utm = "EPSG:32636"

        self.sh_config = SHConfig()
        if hasattr(config, 'CLIENT_ID') and config.CLIENT_ID and config.CLIENT_SECRET:
            self.sh_config.sh_client_id = config.CLIENT_ID
            self.sh_config.sh_client_secret = config.CLIENT_SECRET
        
        print(f"✅ Motor başlatıldı: {self.point}")

    def _get_poi_name(self, row):
        if 'name' in row and pd.notna(row['name']): return row['name']
        if 'brand' in row and pd.notna(row['brand']): return row['brand']
        return "İsimsiz"

    def _clean_osm_data(self, gdf):
        if gdf.empty: return gdf
        for col in ['disused', 'abandoned']:
            if col in gdf.columns: gdf = gdf[gdf[col] != 'yes']
        return gdf

    def _analyze_poi_details(self, category_name, osm_tags, max_radius_m):
        try:
            search_dist = max(max_radius_m, 1500)  # 3000'den 1500'e düşürdük
            gdf = ox.features.features_from_point(center_point=self.point, tags=osm_tags, dist=search_dist)
            gdf = self._clean_osm_data(gdf)
            if gdf.empty: return { "min_dist": float('inf'), "count": 0, "names": [] }
            
            gdf_utm = gdf.to_crs(self.crs_utm)
            point_utm = gpd.GeoSeries([self.point_geom], crs="EPSG:4326").to_crs(self.crs_utm).iloc[0]
            gdf_utm['distance'] = gdf_utm.distance(point_utm)
            gdf_sorted = gdf_utm.sort_values('distance')
            
            min_dist = gdf_sorted.iloc[0]['distance']
            relevant_pois = gdf_sorted[gdf_sorted['distance'] <= max_radius_m]
            count = len(relevant_pois)
            
            # En yakın 3'ün ismini al
            top_names = [self._get_poi_name(row) for _, row in gdf_sorted.head(3).iterrows()]
            
            # Detaylı listeye ekle
            pois_to_save = relevant_pois.head(5) if not relevant_pois.empty else gdf_sorted.head(1)
            for _, row in pois_to_save.iterrows():
                if row['distance'] > 5000: continue
                self.detected_places.append({
                    "kategori": category_name,
                    "isim": self._get_poi_name(row),
                    "mesafe": int(row['distance']),
                    "tur": list(osm_tags.keys())[0]
                })
            
            return { "min_dist": min_dist, "count": count, "names": top_names }
        except Exception:
            return { "min_dist": float('inf'), "count": 0, "names": [] }

    def _calculate_noise_score(self):
        print("  🔊 Gürültü analizi...")
        cfg = self.config.GURULTU_AYARLARI
        max_dist = cfg["max_etki_mesafesi"]
        tags = {}
        for k, v in cfg["ETKENLER"].items(): tags[k] = list(v.keys())
        for k, v in cfg["SONUMLEYICILER"].items():
            tk, tv = k.split('=')
            if tk not in tags: tags[tk] = []
            if tv not in tags[tk]: tags[tk].append(tv)
            
        try:
            pois = ox.features.features_from_point(center_point=self.point, tags=tags, dist=max_dist)
            pois = self._clean_osm_data(pois)
            if pois.empty:
                self.score_details['gurultu'] = {"reason": "Gürültü kaynağı bulunamadı", "closest": None}
                return 100.0
            pois_utm = pois.to_crs(self.crs_utm)
            point_utm = gpd.GeoSeries([self.point_geom], crs="EPSG:4326").to_crs(self.crs_utm).iloc[0]
        except Exception:
            return 100.0
        
        total = 0
        closest_noise = None
        min_noise_dist = float('inf')
        
        for _, poi in pois_utm.iterrows():
            dist = point_utm.distance(poi.geometry)
            if dist > max_dist: continue
            decay = 1 - (dist / max_dist)
            score = 0
            for k, v in cfg["ETKENLER"].items():
                if k in poi and pd.notna(poi[k]) and poi[k] in v: 
                    score = v[poi[k]]
                    if dist < min_noise_dist:
                        min_noise_dist = dist
                        closest_noise = f"{poi[k]} ({int(dist)}m)"
                    break
            total += score * decay
        
        self.score_details['gurultu'] = {
            "reason": "Sessiz bölge" if total < 500 else "Orta gürültü" if total < 2000 else "Yüksek gürültü",
            "closest": closest_noise
        }
        return normalize_linear(total, cfg["min_esik"], cfg["max_esik"], ters=True)

    def _calculate_settlement_score(self):
        print("  🏘️  Yerleşim analizi...")
        cfg = self.config.YERLESIM_AYARLARI
        score = 0
        weight = 0
        details = {}
        
        for name, settings in cfg["etiketler"].items():
            data = self._analyze_poi_details(name, settings["osm_tags"], settings["max_limit"])
            p = normalize_plateau(data["min_dist"], settings["ideal_limit"], settings["max_limit"])
            w = cfg["agirliklar"].get(name, 0)
            score += p * w
            weight += w
            
            # Detay kaydet
            if data["min_dist"] != float('inf'):
                details[name] = {
                    "distance": int(data["min_dist"]),
                    "count": data["count"],
                    "score": round(p, 1),
                    "closest": data["names"][0] if data["names"] else "Bilinmiyor"
                }
        
        self.score_details['yerlesim'] = details
        return score / weight if weight > 0 else 0

    def _calculate_ndvi_score(self):
        print("  🌳 Yeşil alan analizi...")
        val = cache_manager.get_cached_data(self.lat, self.lon, "ndvi")
        if val is None:
            val = 0.3491  # Fallback
            cache_manager.save_data_to_cache(self.lat, self.lon, "ndvi", val)
        
        cfg = self.config.YESIL_SOSYAL_AYARLARI["NDVI"]
        score = normalize_linear(val, cfg["min_esik"], cfg["max_esik"])
        
        self.score_details['ndvi'] = {
            "value": round(val, 2),
            "level": "Yüksek" if val > 0.4 else "Orta" if val > 0.25 else "Düşük"
        }
        return score

    def _calculate_green_social_score(self):
        print("  🎯 Sosyal tesis analizi...")
        cfg = self.config.YESIL_SOSYAL_AYARLARI["POZITIF_ETKENLER"]
        s_ndvi = self._calculate_ndvi_score()
        s_poi = 0
        w_poi = 0
        details = {}
        
        for name, settings in cfg["etiketler"].items():
            max_r = settings.get("max_mesafe", 1000)
            data = self._analyze_poi_details(name, settings["osm_tags"], max_r)
            
            if name == "deniz_kenari":
                self.distance_to_sea = data["min_dist"]
                if self.distance_to_sea == float('inf'): continue
            
            p_yakin = normalize_linear(data["min_dist"], 0, max_r, True)
            p_yogun = min(100, (data["count"]/settings.get("yogunluk_hedefi",1))*100)
            
            w_yakin = cfg.get("yakinlik_agirligi", 0.7)
            w_yogun = cfg.get("yogunluk_agirligi", 0.3)
            final = 0.0
            if data["min_dist"] != float('inf'):
                final = (p_yakin * w_yakin) + (p_yogun * w_yogun)
            
            w = settings.get("agirlik", 1)
            s_poi += final * w
            w_poi += w
            
            # Detay kaydet
            if data["min_dist"] != float('inf'):
                details[name] = {
                    "distance": int(data["min_dist"]),
                    "count": data["count"],
                    "closest": data["names"][0] if data["names"] else "Bilinmiyor"
                }
            
        final_poi = s_poi / w_poi if w_poi > 0 else 0
        w_ndvi = self.config.YESIL_SOSYAL_AYARLARI["NDVI"]["agirlik"]
        w_all = cfg["agirlik"]
        
        self.score_details['sosyal'] = details
        return (s_ndvi * w_ndvi) + (final_poi * w_all)

    def _get_elevations_batch(self, locations):
        try:
            lats = ",".join([str(loc["latitude"]) for loc in locations])
            lons = ",".join([str(loc["longitude"]) for loc in locations])
            url = f"https://api.open-meteo.com/v1/elevation?latitude={lats}&longitude={lons}"
            resp = requests.get(url, timeout=5)  # 3'ten 5'e çıkardık
            if resp.status_code == 200:
                return resp.json()['elevation']
        except Exception:
            return None

    def _calculate_slope_analysis(self):
        print("  ⛰️  Eğim analizi...")
        delta = 0.0015
        points = [
            {"latitude": self.lat, "longitude": self.lon},
            {"latitude": self.lat+delta, "longitude": self.lon},
            {"latitude": self.lat-delta, "longitude": self.lon},
            {"latitude": self.lat, "longitude": self.lon+delta},
            {"latitude": self.lat, "longitude": self.lon-delta}
        ]
        elevs = self._get_elevations_batch(points)
        if not elevs: return {"rakim": "Bilinmiyor", "egim_yuzde": 0, "durum": "Analiz Edilemedi"}
        
        center = elevs[0]
        max_diff = max(abs(h - center) for h in elevs[1:])
        egim = (max_diff / 150) * 100
        
        cfg = self.config.EGIM_AYARLARI["kategoriler"]
        durum = "Bilinmiyor"
        if egim <= cfg["duz"]["max_egim"]: durum = cfg["duz"]["etiket"]
        elif egim <= cfg["hafif"]["max_egim"]: durum = cfg["hafif"]["etiket"]
        elif egim <= cfg["orta"]["max_egim"]: durum = cfg["orta"]["etiket"]
        else: durum = cfg["dik"]["etiket"]
        return { "rakim": center, "egim_yuzde": round(egim, 1), "durum": durum }

    def _calculate_neighborhood_vibe(self):
        print("  🏘️  Mahalle karakteri...")
        cfg = self.config.VIBE_AYARLARI
        scores = {"aile": 0, "sosyal": 0, "ticari": 0}
        for name, data in cfg["kategoriler"].items():
            try:
                gdf = ox.features.features_from_point(self.point, data["tags"], dist=cfg["yaricap"])
                gdf = self._clean_osm_data(gdf)
                scores[name] = len(gdf)
            except Exception:
                scores[name] = 0
        sorted_s = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        if sorted_s[0][1] < 3: return {"etiket": "🍃 Sakin / Gelişmekte Olan", "aciklama": "Sessiz bir bölge."}
        if sorted_s[1][1] > (sorted_s[0][1] * 0.7): return {"etiket": "🔄 Karma Yaşam (Canlı)", "aciklama": "Çok yönlü bir mahalle."}
        return {"etiket": cfg["kategoriler"][sorted_s[0][0]]["etiket"], "aciklama": cfg["kategoriler"][sorted_s[0][0]]["aciklama"]}

    def get_final_score(self):
        print("\n🚀 MOTOR BAŞLATILDI (v4.2.0 - Hızlı)")
        self.detected_places = []
        
        # Paralel hesaplama
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            f1 = executor.submit(self._calculate_noise_score)
            f2 = executor.submit(self._calculate_settlement_score)
            f3 = executor.submit(self._calculate_green_social_score)
            
            s_gurultu = f1.result()
            s_yerlesim = f2.result()
            s_sosyal = f3.result()
        
        # Sıralı hesaplama (daha hızlı)
        a_egim = self._calculate_slope_analysis()
        a_vibe = self._calculate_neighborhood_vibe()

        cfg = self.config.FINAL_AGIRLIKLAR
        genel = (s_sosyal * cfg["yesil_sosyal"] + s_yerlesim * cfg["yerlesim"] + s_gurultu * cfg["gurultu"])
        
        print("✅ MOTOR TAMAMLANDI")
        return {
            "genel_skor": genel,
            "alt_skorlar": { "yesil_sosyal": s_sosyal, "yerlesim": s_yerlesim, "gurultu": s_gurultu },
            "ekstra_analiz": { "egim": a_egim, "vibe": a_vibe },
            "mekanlar": self.detected_places,
            "detaylar": self.score_details  # YENI!
        }
