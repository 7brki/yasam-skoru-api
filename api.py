# api.py (v3.5 Final - CORS & Lists)

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import time
from scorer import QualityScorer
import config as cfg
import os

# GÜVENLİK: Anahtarları ortam değişkenlerinden al (Render için)
if not cfg.CLIENT_ID: cfg.CLIENT_ID = os.environ.get("SH_CLIENT_ID")
if not cfg.CLIENT_SECRET: cfg.CLIENT_SECRET = os.environ.get("SH_CLIENT_SECRET")

app = FastAPI(title="Yaşam Kalitesi Skoru API", version="3.5.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SkorIstegi(BaseModel):
    lat: float
    lon: float

@app.get("/")
def ana_sayfa():
    return {"durum": "aktif", "mesaj": "API Çalışıyor."}

@app.post("/hesapla")
def skor_hesapla(istek: SkorIstegi):
    print(f"--> İSTEK: {istek.lat}, {istek.lon}")
    start = time.time()
    try:
        motor = QualityScorer(istek.lat, istek.lon, cfg)
        res = motor.get_final_score()
        dur = round(time.time() - start, 2)
        
        mekanlar = sorted(res.get("mekanlar", []), key=lambda x: x["mesafe"])
        detay = res['ekstra_analiz'].get('egim', {})
        vibe = res['ekstra_analiz'].get('vibe', {})
        
        return {
            "durum": "basarili",
            "meta": { "islem_suresi": f"{dur} saniye", "koordinat": {"lat": istek.lat, "lon": istek.lon} },
            "ozellikler": {
                "cografya": { "rakim": f"{detay.get('rakim',0)}m", "yurunebilirlik": detay.get('durum','-'), "egim_orani": f"%{detay.get('egim_yuzde',0)}" },
                "mahalle_karakteri": { "etiket": vibe.get('etiket','-'), "aciklama": vibe.get('aciklama','-') }
            },
            "yakin_yerler": mekanlar,
            "skor_ozeti": {
                "genel_skor": round(res["genel_skor"], 1),
                "detaylar": {
                    "yesil_sosyal": round(res["alt_skorlar"]["yesil_sosyal"], 1),
                    "yerlesim": round(res["alt_skorlar"]["yerlesim"], 1),
                    "gurultu": round(res["alt_skorlar"]["gurultu"], 1),
                    "hava_kalitesi": "Veri Yok"
                }
            }
        }
    except Exception as e:
        print(f"HATA: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
