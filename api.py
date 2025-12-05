# api.py (v4.2.0 - AI FIX + DETAYLI SKORLAR)
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import time
import requests
import os
from scorer import QualityScorer
import config as cfg

# --- GÜVENLİK ---
if not cfg.CLIENT_ID: cfg.CLIENT_ID = os.environ.get("SH_CLIENT_ID")
if not cfg.CLIENT_SECRET: cfg.CLIENT_SECRET = os.environ.get("SH_CLIENT_SECRET")

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

app = FastAPI(title="Yaşam Kalitesi Skoru API", version="4.2.0")

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

def generate_ai_comment(skorlar, ozellikler, detaylar):
    """AI yorumu üret - hata kontrolü ile"""
    
    # KEY KONTROLÜ
    if not GEMINI_API_KEY or GEMINI_API_KEY == "None":
        print("⚠️  GEMINI_API_KEY bulunamadı!")
        return "🏠 Bu konum harika görünüyor! Detaylı analiz için skorları inceleyin."
    
    # Detaylardan bilgi çıkar
    yakin_mekanlar = []
    if 'sosyal' in detaylar and detaylar['sosyal']:
        for k, v in list(detaylar['sosyal'].items())[:2]:
            yakin_mekanlar.append(f"{v['closest']} ({v['distance']}m)")
    
    prompt_text = f"""
    Sen bir emlak danışmanısın. Bu evi 2 kısa cümleyle tanıt:
    
    SKORLAR:
    - Genel: {skorlar['genel_skor']}/100
    - Mahalle: {ozellikler['mahalle_karakteri']['etiket']}
    - Gürültü: {skorlar['detaylar']['gurultu']}/100 (Yüksek=Sessiz)
    - Arazi: {ozellikler['cografya']['yurunebilirlik']}
    
    YAKIN MEKANLAR: {', '.join(yakin_mekanlar) if yakin_mekanlar else 'Veri yok'}
    
    İki cümleyle, samimi ve ikna edici şekilde yaz. Türkçe.
    """
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    
    payload = {
        "contents": [{
            "parts": [{"text": prompt_text}]
        }],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 150
        }
    }
    
    try:
        print("🤖 AI isteği gönderiliyor...")
        response = requests.post(url, json=payload, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            yorum = data['candidates'][0]['content']['parts'][0]['text']
            print("✅ AI yorumu alındı!")
            return yorum.strip()
        elif response.status_code == 400:
            print(f"❌ AI Hatası: API Key geçersiz - {response.text}")
            return "🏠 Güzel bir konum! Skorları inceleyerek daha fazla bilgi alabilirsiniz."
        else:
            print(f"⚠️  AI HTTP {response.status_code}: {response.text[:200]}")
            return "🏠 Konumunuz analiz edildi! Detaylı skorları aşağıda görebilirsiniz."
            
    except requests.Timeout:
        print("⏱️  AI timeout!")
        return "🏠 Harika bir konum! Detaylı analize göz atın."
    except Exception as e:
        print(f"❌ AI Hatası: {e}")
        return "🏠 Veriler başarıyla analiz edildi!"

@app.get("/")
def ana_sayfa():
    ai_status = "aktif ✅" if GEMINI_API_KEY and GEMINI_API_KEY != "None" else "pasif ⚠️"
    return {
        "durum": "aktif",
        "mesaj": "API v4.2 (Hızlı + Detaylı)",
        "ai_durumu": ai_status,
        "ozellikler": ["Hızlı Analiz", "Detaylı Skorlar", "AI Yorumu"]
    }

@app.post("/hesapla")
def skor_hesapla(istek: SkorIstegi):
    print(f"\n📍 İstek geldi: {istek.lat}, {istek.lon}")
    baslangic = time.time()
    
    try:
        motor = QualityScorer(lat=istek.lat, lon=istek.lon, config=cfg)
        sonuc = motor.get_final_score()
        
        analiz_egim = sonuc['ekstra_analiz'].get('egim', {})
        analiz_vibe = sonuc['ekstra_analiz'].get('vibe', {})
        mekanlar = sorted(sonuc.get("mekanlar", []), key=lambda x: x["mesafe"])
        detaylar = sonuc.get("detaylar", {})
        
        cevap_data = {
            "ozellikler": {
                "cografya": {
                    "rakim": f"{analiz_egim.get('rakim', '0')}m",
                    "yurunebilirlik": analiz_egim.get('durum', '-'),
                    "egim_orani": f"%{analiz_egim.get('egim_yuzde', 0)}"
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
            },
            "detayli_analiz": detaylar  # YENI!
        }
        
        # AI Yorumunu Al
        cevap_data["ai_yorumu"] = generate_ai_comment(
            cevap_data["skor_ozeti"], 
            cevap_data["ozellikler"],
            detaylar
        )
        
        sure = round(time.time() - baslangic, 2)
        print(f"✅ Tamamlandı ({sure}s)")
        
        return {
            "durum": "basarili",
            "meta": {
                "islem_suresi": f"{sure} saniye",
                "koordinat": {"lat": istek.lat, "lon": istek.lon}
            },
            **cevap_data,
            "yakin_yerler": mekanlar
        }

    except Exception as e:
        print(f"❌ HATA: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
