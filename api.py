# api.py
# (v3.7.0 - STABIL SURUM: google-generativeai + gemini-pro)

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import time
# --- ESKİ AMA GÜVENİLİR KÜTÜPHANE ---
import google.generativeai as genai
# ------------------------------------
from scorer import QualityScorer
import config as cfg
import os

# --- GÜVENLİK ---
if not cfg.CLIENT_ID: cfg.CLIENT_ID = os.environ.get("SH_CLIENT_ID")
if not cfg.CLIENT_SECRET: cfg.CLIENT_SECRET = os.environ.get("SH_CLIENT_SECRET")

# --- YAPAY ZEKA AYARLARI ---
# BURAYA YENİ ALDIĞIN ANAHTARI YAPIŞTIR
GEMINI_API_KEY = "AIzaSyDs23xhaclr2WsKnrp15v4ow8l3TQYgdcI" 

try:
    genai.configure(api_key=GEMINI_API_KEY)
except Exception as e:
    print(f"AI Config Hatası: {e}")

app = FastAPI(title="Yaşam Kalitesi Skoru API", version="3.7.0")

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

def generate_ai_comment(skorlar, ozellikler):
    prompt = f"""
    Sen bir Gayrimenkul Danışmanısın. Şu verilere göre bu mülkü 2 cümlede özetle:
    Genel Puan: {skorlar['genel_skor']}/100, Gürültü: {skorlar['detaylar']['gurultu']} (Yüksek=Sessiz),
    Yürüyüş: {ozellikler['cografya']['yurunebilirlik']}, Karakter: {ozellikler['mahalle_karakteri']['etiket']}.
    Olumlu konuş. Türkçe cevap ver.
    """
    
    # SADECE BU İKİ MODELİ DENİYORUZ (EN STABİL OLANLAR)
    models = ['gemini-pro', 'gemini-1.5-flash']
    
    for m in models:
        try:
            print(f"AI deneniyor: {m}...")
            model = genai.GenerativeModel(m)
            response = model.generate_content(prompt)
            if response and response.text:
                return response.text
        except Exception as e:
            print(f"Hata ({m}): {e}")
            continue

    return "Yapay zeka şu anda yoğun, ancak veriler harika görünüyor!"

@app.get("/")
def ana_sayfa():
    return {"durum": "aktif", "mesaj": "API v3.7 Çalışıyor."}

@app.post("/hesapla")
def skor_hesapla(istek: SkorIstegi):
    print(f"--> API İsteği Geldi: {istek.lat}, {istek.lon}")
    baslangic = time.time()
    try:
        motor = QualityScorer(lat=istek.lat, lon=istek.lon, config=cfg)
        sonuc = motor.get_final_score()
        
        analiz_detay = sonuc['ekstra_analiz'].get('detay', {})
        analiz_vibe = sonuc['ekstra_analiz'].get('vibe', {})
        mekanlar = sorted(sonuc.get("mekanlar", []), key=lambda x: x["mesafe"])
        
        cevap_data = {
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
            "skor_ozeti": {
                "genel_skor": round(sonuc["genel_skor"], 1),
                "detaylar": {
                    "yesil_sosyal": round(sonuc["alt_skorlar"]["yesil_sosyal"], 1),
                    "yerlesim": round(sonuc["alt_skorlar"]["yerlesim"], 1),
                    "gurultu": round(sonuc["alt_skorlar"]["gurultu"], 1)
                }
            }
        }
        cevap_data["ai_yorumu"] = generate_ai_comment(cevap_data["skor_ozeti"], cevap_data["ozellikler"])
        
        return {
            "durum": "basarili",
            "meta": { "islem_suresi": f"{round(time.time() - baslangic, 2)} saniye" },
            **cevap_data,
            "yakin_yerler": mekanlar
        }

    except Exception as e:
        print(f"KRİTİK HATA: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
