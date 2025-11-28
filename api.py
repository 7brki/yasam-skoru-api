# api.py
# (v3.5.0 - CORS DÜZELTMESİ EKLENDİ)

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware # <-- BU SATIR ÇOK ÖNEMLİ
from pydantic import BaseModel
import uvicorn
import time
from scorer import QualityScorer
import config as cfg
import os

# --- GÜVENLİK ---
# Render'da Environment Variable yoksa hata vermemesi için kontrol
if not cfg.CLIENT_ID:
    cfg.CLIENT_ID = os.environ.get("SH_CLIENT_ID")
if not cfg.CLIENT_SECRET:
    cfg.CLIENT_SECRET = os.environ.get("SH_CLIENT_SECRET")

app = FastAPI(
    title="Yaşam Kalitesi Skoru API",
    description="Emlak değerleme motoru (v3.5)",
    version="3.5.0"
)

# --- KRİTİK DÜZELTME: CORS AYARLARI ---
# Bu blok, tarayıcının (GitHub Pages) sunucuya (Render) erişmesine izin verir.
# OPTIONS isteğine 200 OK dönmesini sağlar.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Tüm sitelere izin ver
    allow_credentials=True,
    allow_methods=["*"], # GET, POST, OPTIONS hepsine izin ver
    allow_headers=["*"], # Tüm başlıklara izin ver
)
# -------------------------------------

class SkorIstegi(BaseModel):
    lat: float
    lon: float

@app.get("/")
def ana_sayfa():
    return {"durum": "aktif", "mesaj": "CORS ayarları aktif. API kullanıma hazır."}

@app.post("/hesapla")
def skor_hesapla(istek: SkorIstegi):
    print(f"--> API İsteği Geldi: {istek.lat}, {istek.lon}")
    baslangic = time.time()
    
    try:
        motor = QualityScorer(lat=istek.lat, lon=istek.lon, config=cfg)
        sonuc = motor.get_final_score()
        sure = round(time.time() - baslangic, 2)
        
        analiz_detay = sonuc['ekstra_analiz'].get('detay', {})
        analiz_vibe = sonuc['ekstra_analiz'].get('vibe', {})
        
        # Mekan listesini hazırla
        mekanlar = sorted(sonuc.get("mekanlar", []), key=lambda x: x["mesafe"])
        
        cevap = {
            "durum": "basarili",
            "meta": {
                "islem_suresi": f"{sure} saniye",
                "koordinat": {"lat": istek.lat, "lon": istek.lon}
            },
            "ozellikler": {
                "cografya": {
                    "rakim": f"{analiz_detay.get('rakim', '0')}m",
                    "yurunebilirlik": analiz_detay.get('durum', '-'),
                    "egim_orani": f"%{analiz_detay.get('egim_yuzde', 0)}"
                },
                "mahalle_karakteri": {
                    "etiket": analiz_vibe.get('etiket', '-'),
                    "aciklama": analiz_vibe.get('aciklama', '-')
                }
            },
            "yakin_yerler": mekanlar,
            "skor_ozeti": {
                "genel_skor": round(sonuc["genel_skor"], 1),
                "detaylar": {
                    "yesil_sosyal": round(sonuc["alt_skorlar"]["yesil_sosyal"], 1),
                    "yerlesim": round(sonuc["alt_skorlar"]["yerlesim"], 1),
                    "gurultu": round(sonuc["alt_skorlar"]["gurultu"], 1)
                }
            }
        }
        return cevap

    except Exception as e:
        print(f"KRİTİK HATA: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
