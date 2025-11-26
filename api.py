# api.py
# (v3.2.0 Final API - Manzara Tahmini Çıkarıldı)

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
import time
from scorer import QualityScorer
import config as cfg

app = FastAPI(
    title="Yaşam Kalitesi Skoru API",
    description="Emlak değerleme için Yakınlık + Yoğunluk + Topografya bazlı yapay zeka motoru (v3.2)",
    version="3.2.0"
)


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