def _calculate_ndvi_score(self):
    print("  -> Yeşil/Sosyal (NDVI): Veri kontrol ediliyor...")
    val = cache_manager.get_cached_data(self.lat, self.lon, "ndvi")
    
    if val is None:
        print("  -> [CACHE MISS] Sentinel Hub'a bağlanılıyor...")
        val = self._fetch_satellite_data()  # Gerçek veri çekimi
        
        if val is not None:
            cache_manager.save_data_to_cache(self.lat, self.lon, "ndvi", val)
            print(f"  -> [UYDU VERİSİ] NDVI: {val:.4f}")
        else:
            print("  -> [UYARI] Uydu verisi alınamadı, varsayılan kullanılıyor.")
            val = 0.3491  # Fallback
    else: 
        print(f"  -> [CACHE HIT] NDVI: {val:.4f}")
    
    cfg = self.config.YESIL_SOSYAL_AYARLARI["NDVI"]
    return normalize_linear(val, cfg["min_esik"], cfg["max_esik"])

def _fetch_satellite_data(self):
    """Sentinel Hub'dan NDVI verisi çeker."""
    try:
        from sentinelhub import SentinelHubRequest, DataCollection, MimeType, bbox_to_dimensions
        
        # API Key kontrolü
        if not self.sh_config.sh_client_id or not self.sh_config.sh_client_secret:
            print("  -> ⚠️  Sentinel Hub API anahtarları bulunamadı!")
            return None
        
        evalscript = """
        //VERSION=3
        function setup() { return { input: ["B04", "B08"], output: { bands: 1 } }; }
        function evaluatePixel(sample) {
            let ndvi = (sample.B08 - sample.B04) / (sample.B08 + sample.B04);
            return [ndvi];
        }
        """
        
        size = bbox_to_dimensions(self.bbox, resolution=10)
        
        request = SentinelHubRequest(
            evalscript=evalscript,
            input_data=[
                SentinelHubRequest.input_data(
                    data_collection=DataCollection.SENTINEL2_L2A,
                    time_interval=('2024-01-01', '2024-12-31'),
                    maxcc=0.3
                )
            ],
            responses=[SentinelHubRequest.output_response('default', MimeType.TIFF)],
            bbox=self.bbox,
            size=size,
            config=self.sh_config
        )
        
        data = request.get_data()[0]
        ndvi_avg = float(data.mean())
        
        return ndvi_avg
        
    except Exception as e:
        print(f"  -> ❌ Sentinel Hub hatası: {e}")
        return None
