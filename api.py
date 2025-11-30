# api.py
# (v3.6.1 - Final Sürüm: CORS + AI Yedekleme + Detaylı Liste)

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import time
import google.generativeai as genai
from scorer import QualityScorer
import config as cfg
import os

# --- GÜVENLİK (SENTINEL HUB) ---
# Render'da Environment Variables yoksa hata vermemesi için kontrol
if not cfg.CLIENT_ID: cfg.CLIENT_ID = os.environ.get("SH_CLIENT_ID")
if not cfg.CLIENT_SECRET: cfg.CLIENT_SECRET = os.environ.get("SH_CLIENT_SECRET")

# --- YAPAY ZEKA AYARLARI (GOOGLE GEMINI) ---
# DİKKAT: Buraya Google AI Studio'dan aldığın API anahtarını yapıştır.
GEMINI_API_KEY = "AIzaSyDewXK4gL3w8Di4yE3oVPZBxeFhwK8MTzM" 

try:
    genai.configure(api_key=GEMINI_API_KEY)
except Exception as e:
    print(f"AI Config Hatası: {e}")

app = FastAPI(
    title="Yaşam Kalitesi Skoru API", 
    description="Emlak değerleme motoru (v3.6)",
    version="3.6.1"
)

# --- CORS AYARLARI (BAĞLANTI İÇİN ŞART) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Tüm sitelere (GitHub Pages dahil) izin ver
    allow_credentials=True,
    allow_methods=["*"], 
    allow_headers=["*"], 
)

class SkorIstegi(BaseModel):
    lat: float
    lon: float

def generate_ai_comment(skorlar, ozellikler):
    """
    Yapay zeka yorumu üretir. Hata alırsak yedek modellere geçer.
    """
    prompt = f"""
    Sen profesyonel bir Emlak Danışmanısın. Aşağıdaki verilere göre bu evi potansiyel alıcıya 2 kısa cümlede özetle:
    
    - Genel Puan: {skorlar['genel_skor']}/100
    - Gürültü: {skorlar['detaylar']['gurultu']} (Yüksek puan sessiz demek)
    - Erişim: {skorlar['detaylar']['yerlesim']}
    - Sosyal: {skorlar['detaylar']['yesil_sosyal']}
    - Yürünebilirlik: {ozellikler['cografya']['yurunebilirlik']}
    - Mahalle: {ozellikler['mahalle_karakteri']['etiket']}
    
    Tonun samimi, pozitif ve satış odaklı olsun. Türkçe cevap ver.
    """
    
    # Denenecek modeller (Yeniden eskiye)
    models_to_try = ['gemini-1.5-flash', 'gemini-pro', 'gemini-1.0-pro']
    
    for model_name in models_to_try:
        try:
            print(f"AI deneniyor: {model_name}...")
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            if response and response.text:
                return response.text
        except Exception as e:
            print(f"Model Hatası ({model_name}): {e}")
            continue

    return "Yapay zeka şu anda yoğun, ancak veriler harika görünüyor! (AI Bağlantı Hatası)"

@app.get("/")
def ana_sayfa():
    return {"durum": "aktif", "mesaj": "API v3.6.1 Çalışıyor (CORS + AI Fix)."}

@app.post("/hesapla")
def skor_hesapla(istek: SkorIstegi):
    print(f"--> API İsteği Geldi: {istek.lat}, {istek.lon}")
    baslangic = time.time()
    
    try:
        # 1. Motoru Başlat
        motor = QualityScorer(lat=istek.lat, lon=istek.lon, config=cfg)
        
        # 2. Hesapla
        sonuc = motor.get_final_score()
        
        # 3. Verileri Hazırla
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
        
        # 4. AI Yorumu Ekle
        cevap_data["ai_yorumu"] = generate_ai_comment(cevap_data["skor_ozeti"], cevap_data["ozellikler"])
        
        # 5. Final JSON
        final_response = {
            "durum": "basarili",
            "meta": {
                "islem_suresi": f"{round(time.time() - baslangic, 2)} saniye",
                "koordinat": {"lat": istek.lat, "lon": istek.lon},
                "algoritma": "v3.6_final"
            },
            **cevap_data,
            "yakin_yerler": mekanlar
        }
        
        return final_response

    except Exception as e:
        print(f"KRİTİK API HATASI: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
