# api.py
# (v4.1.0 - NO-SDK MODU: Doğrudan HTTP İsteği)
# Google kütüphanesi yerine 'requests' kullanarak versiyon sorununu kökten çözer.

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import time
import requests # <-- Artık Google kütüphanesi yerine standart istek atıyoruz
import json
from scorer import QualityScorer
import config as cfg
import os

# --- GÜVENLİK ---
if not cfg.CLIENT_ID: cfg.CLIENT_ID = os.environ.get("SH_CLIENT_ID")
if not cfg.CLIENT_SECRET: cfg.CLIENT_SECRET = os.environ.get("SH_CLIENT_SECRET")

# Anahtarı koddan değil, sunucunun kasasından (Environment Variable) çekiyoruz
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# Eğer sunucuda anahtar yoksa hata vermemesi için bir kontrol ekleyelim
if not GEMINI_API_KEY:
    print("UYARI: GEMINI_API_KEY ortam değişkeni bulunamadı!")

app = FastAPI(title="Yaşam Kalitesi Skoru API", version="4.1.0")

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
    Google Gemini API'ye kütüphanesiz, doğrudan HTTP (REST) isteği atar.
    Bu yöntem kütüphane sürümünden etkilenmez.
    """
    
    # Prompt Metni
    prompt_text = f"""
    Sen bir Emlak Danışmanısın. Bu verileri kullanarak evi 2 kısa, vurucu cümleyle özetle:
    - Genel Puan: {skorlar['genel_skor']}/100
    - Konum: {ozellikler['mahalle_karakteri']['etiket']}
    - Gürültü: {skorlar['detaylar']['gurultu']} (Yüksek puan = Sessiz)
    - Yürünebilirlik: {ozellikler['cografya']['yurunebilirlik']}
    
    Samimi ve satış odaklı ol. Türkçe cevap ver.
    """
    
    # Google REST API Adresi (Model: gemini-1.5-flash)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    
    # İstek Gövdesi
    payload = {
        "contents": [{
            "parts": [{"text": prompt_text}]
        }]
    }
    
    try:
        print("🤖 AI İsteği gönderiliyor (Raw HTTP)...")
        # 5 saniye timeout koyuyoruz ki sistem kilitlenmesin
        response = requests.post(url, json=payload, timeout=8)
        
        if response.status_code == 200:
            data = response.json()
            # Google'ın JSON yapısından metni çıkar
            yorum = data['candidates'][0]['content']['parts'][0]['text']
            return yorum
        else:
            print(f"⚠️ AI HTTP Hatası: {response.status_code} - {response.text}")
            return "Yapay zeka şu anda meşgul, ama veriler harika görünüyor!"
            
    except Exception as e:
        print(f"❌ AI Bağlantı Hatası: {e}")
        return "Yapay zeka yorumu alınamadı."

@app.get("/")
def ana_sayfa():
    return {"durum": "aktif", "mesaj": "API v4.1 (Raw HTTP AI) Çalışıyor."}

@app.post("/hesapla")
def skor_hesapla(istek: SkorIstegi):
    print(f"--> API İsteği Geldi: {istek.lat}, {istek.lon}")
    baslangic = time.time()
    
    try:
        # Motoru Başlat
        motor = QualityScorer(lat=istek.lat, lon=istek.lon, config=cfg)
        
        # Skoru Hesapla
        sonuc = motor.get_final_score()
        
        # Verileri Hazırla
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
        
        # AI Yorumunu Al (Yeni Yöntem)
        cevap_data["ai_yorumu"] = generate_ai_comment(cevap_data["skor_ozeti"], cevap_data["ozellikler"])
        
        final_response = {
            "durum": "basarili",
            "meta": {
                "islem_suresi": f"{round(time.time() - baslangic, 2)} saniye",
                "koordinat": {"lat": istek.lat, "lon": istek.lon},
                "algoritma": "v4.1_raw_http"
            },
            **cevap_data,
            "yakin_yerler": mekanlar
        }
        
        return final_response

    except Exception as e:
        print(f"KRİTİK HATA: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
