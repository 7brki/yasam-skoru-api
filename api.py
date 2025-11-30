# api.py
# (v3.6.0 - YAPAY ZEKA YORUMCUSU EKLENDİ)

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import time
import google.generativeai as genai # YENİ KÜTÜPHANE
from scorer import QualityScorer
import config as cfg
import os

# --- GÜVENLİK ---
if not cfg.CLIENT_ID: cfg.CLIENT_ID = os.environ.get("SH_CLIENT_ID")
if not cfg.CLIENT_SECRET: cfg.CLIENT_SECRET = os.environ.get("SH_CLIENT_SECRET")

# --- YAPAY ZEKA AYARLARI ---
# Buraya Google AI Studio'dan aldığın anahtarı yapıştır
GEMINI_API_KEY = "AIzaSyDewXK4gL3w8Di4yE3oVPZBxeFhwK8MTzM" 

genai.configure(api_key=GEMINI_API_KEY)

app = FastAPI(title="Yaşam Kalitesi Skoru API", version="3.6.0")

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
    Skorları ve özellikleri Gemini'ye gönderip emlakçı yorumu alır.
    """
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        prompt = f"""
        Sen deneyimli, samimi ve profesyonel bir Gayrimenkul Danışmanısın.
        Aşağıdaki verilere dayanarak, bu mülk hakkında potansiyel alıcıya 2-3 cümlelik özet bir yorum yap.
        
        VERİLER:
        - Genel Yaşam Skoru: {skorlar['genel_skor']}/100
        - Yeşil Alan/Sosyal: {skorlar['detaylar']['yesil_sosyal']}/100
        - Yerleşim/Erişim: {skorlar['detaylar']['yerlesim']}/100
        - Gürültü Seviyesi: {skorlar['detaylar']['gurultu']}/100 (Yüksek puan = Sessiz, Düşük puan = Gürültülü)
        - Yürünebilirlik: {ozellikler['cografya']['yurunebilirlik']}
        - Mahalle Havası: {ozellikler['mahalle_karakteri']['etiket']}
        
        YORUM TONU:
        - Samimi ama profesyonel ol.
        - Verileri tekrar etme (örneğin "puanı 80" deme), yorumla.
        - Olumlu yönleri öne çıkar, olumsuzlukları nazikçe belirt.
        - Türkçe cevap ver.
        """
        
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"AI Hatası: {e}")
        return "Yapay zeka şu anda yorum yapamıyor, ancak veriler harika görünüyor!"

@app.get("/")
def ana_sayfa():
    return {"durum": "aktif", "mesaj": "API v3.6 (AI Destekli) Çalışıyor."}

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
        
        # JSON Veri Yapısı
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
        
        # --- YAPAY ZEKA YORUMU EKLE ---
        # Veriler hazır olduktan sonra AI'ya gönderiyoruz
        ai_yorumu = generate_ai_comment(cevap_data["skor_ozeti"], cevap_data["ozellikler"])
        
        # Yorumu cevaba ekle
        cevap_data["ai_yorumu"] = ai_yorumu
        
        # Meta veriyi ve dış yapıyı oluştur
        final_response = {
            "durum": "basarili",
            "meta": {
                "islem_suresi": f"{round(time.time() - baslangic, 2)} saniye",
                "koordinat": {"lat": istek.lat, "lon": istek.lon},
                "algoritma": "v3.6_ai_commentary"
            },
            **cevap_data, # Verileri birleştir
            "yakin_yerler": mekanlar
        }
        
        return final_response

    except Exception as e:
        print(f"KRİTİK API HATASI: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

