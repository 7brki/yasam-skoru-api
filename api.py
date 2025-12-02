# api.py
# (v4.0.0 - NEXT GEN AI: Google GenAI SDK & Gemini 2.0/3.0)

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import time
# --- YENİ KÜTÜPHANE ---
from google import genai
from google.genai import types
# ----------------------
from scorer import QualityScorer
import config as cfg
import os

# --- GÜVENLİK ---
if not cfg.CLIENT_ID: cfg.CLIENT_ID = os.environ.get("SH_CLIENT_ID")
if not cfg.CLIENT_SECRET: cfg.CLIENT_SECRET = os.environ.get("SH_CLIENT_SECRET")

# --- YAPAY ZEKA AYARLARI ---
GEMINI_API_KEY = "AIzaSyDewXK4gL3w8Di4yE3oVPZBxeFhwK8MTzM" # (Veya os.environ'dan çek)

app = FastAPI(title="Yaşam Kalitesi Skoru API", version="4.0.0")

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
    """
    Yeni Google GenAI SDK kullanarak yorum üretir.
    Gemini 3.0 ve 2.0 modellerini önceliklendirir.
    """
    prompt = f"""
    Sen bir Gayrimenkul Danışmanısın. Şu verilere göre bu mülkü 2 kısa cümlede özetle:
    
    - Genel Puan: {skorlar['genel_skor']}/100
    - Gürültü: {skorlar['detaylar']['gurultu']} (Yüksek puan sessiz demek)
    - Erişim: {skorlar['detaylar']['yerlesim']}
    - Sosyal: {skorlar['detaylar']['yesil_sosyal']}
    - Yürünebilirlik: {ozellikler['cografya']['yurunebilirlik']}
    - Mahalle: {ozellikler['mahalle_karakteri']['etiket']}
    
    Tonun samimi, pozitif ve satış odaklı olsun. Türkçe cevap ver.
    """
    
    # 2025 Standartlarında Model Listesi
    models_to_try = [
        'gemini-2.0-flash-exp', # En hızlı ve yeni
        'gemini-2.0-flash',
        'gemini-1.5-flash',      # Stabil yedek
        'gemini-1.5-pro'
    ]
    
    # Yeni Client Yapısı
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        print(f"Client Başlatma Hatası: {e}")
        return "AI Bağlantı Hatası."

    for model_name in models_to_try:
        try:
            print(f"AI deneniyor: {model_name}...")
            
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.7, # Biraz yaratıcılık
                    max_output_tokens=100
                )
            )
            
            if response and response.text:
                return response.text
                
        except Exception as e:
            print(f"Model Hatası ({model_name}): {e}")
            continue

    return "Yapay zeka şu anda yoğun, ancak veriler harika görünüyor!"

@app.get("/")
def ana_sayfa():
    return {"durum": "aktif", "mesaj": "API v4.0 (Next-Gen AI) Çalışıyor."}

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
        
        # AI Yorumu
        cevap_data["ai_yorumu"] = generate_ai_comment(cevap_data["skor_ozeti"], cevap_data["ozellikler"])
        
        final_response = {
            "durum": "basarili",
            "meta": {
                "islem_suresi": f"{round(time.time() - baslangic, 2)} saniye",
                "koordinat": {"lat": istek.lat, "lon": istek.lon},
                "algoritma": "v4.0_genai_sdk"
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
