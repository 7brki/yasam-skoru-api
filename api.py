# api.py
# (v3.3.0 - CORS İzinleri Eklendi)

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware # <-- YENİ EKLENDİ
from pydantic import BaseModel
import uvicorn
import time
from scorer import QualityScorer
import config as cfg

# ... (Güvenlik ve Config kısımları aynı) ...

app = FastAPI(
    title="Yaşam Kalitesi Skoru API",
    description="Emlak değerleme motoru (v3.3)",
    version="3.3.0"
)

# --- YENİ: CORS AYARLARI (BAĞLANTI İÇİN ŞART) ---
# Bu blok, tarayıcının API'ye erişmesine izin verir.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # "*" = Herkese izin ver (Güvenlik için ileride site adresinle değiştirirsin)
    allow_credentials=True,
    allow_methods=["*"], # GET, POST vb. hepsine izin ver
    allow_headers=["*"],
)
# ------------------------------------------------

# ... (Geri kalan kodlar AYNI kalsın: class SkorIstegi, @app.get, @app.post vb.) ...
# (Kodun tamamını tekrar yapıştırmana gerek yok, sadece app = FastAPI(...) altına
# yukarıdaki add_middleware bloğunu ekle ve en üste import'u ekle yeterli.)

class SkorIstegi(BaseModel):
    lat: float
    lon: float


@app.get("/")
def ana_sayfa():
    return {"durum": "aktif", "mesaj": "Yaşam Kalitesi Skoru API (v3.2) Çalışıyor.",
            "kullanim": "/docs adresine giderek test edebilirsiniz."}


@app.post("/hesapla")
def skor_hesapla(istek: SkorIstegi):
    baslangic = time.time()
    print(f"--> API İsteği Geldi: {istek.lat}, {istek.lon}")

    try:
        motor = QualityScorer(lat=istek.lat, lon=istek.lon, config=cfg)
        sonuc = motor.get_final_score()
        sure = round(time.time() - baslangic, 2)

        cevap = {
            "durum": "basarili",
            "meta": {
                "islem_suresi": f"{sure} saniye",
                "koordinat": {"lat": istek.lat, "lon": istek.lon},
                "algoritma": "v3.2_sade_model"
            },
            "ozellikler": {
                "cografya": {
                    "rakim": f"{sonuc['ekstra_analiz']['egim']['rakim']}m",
                    "yurunebilirlik": sonuc['ekstra_analiz']['egim']['durum'],
                    "egim_orani": f"%{sonuc['ekstra_analiz']['egim']['egim_yuzde']}"
                },
                "mahalle_karakteri": {
                    "etiket": sonuc['ekstra_analiz']['vibe']['etiket'],
                    "aciklama": sonuc['ekstra_analiz']['vibe']['aciklama']
                }
            },
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
        print(f"KRİTİK API HATASI: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
