import sqlite3
import requests
import pandas as pd
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from apscheduler.schedulers.background import BackgroundScheduler

app = FastAPI()

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "kocaeli_hava.db"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

KOCAELI_LAT = 40.7654
KOCAELI_LON = 29.9408

def init_db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS hava_durumu (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sehir TEXT,
            sicaklik REAL,
            nem REAL,
            zaman TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    conn.close()

def veri_cek_ve_kaydet_gorevi():
    try:
        url = f"https://api.open-meteo.com/v1/forecast?latitude={KOCAELI_LAT}&longitude={KOCAELI_LON}&current=temperature_2m,relative_humidity_2m"
        res = requests.get(url, timeout=10).json()
        
        sicaklik = res["current"]["temperature_2m"]
        nem = res["current"]["relative_humidity_2m"]

        conn = sqlite3.connect(str(DB_PATH))
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO hava_durumu (sehir, sicaklik, nem) VALUES (?, ?, ?);",
            ("Kocaeli", sicaklik, nem)
        )
        conn.commit()
        conn.close()
        print(f"[OTOMATİK İŞ] Kocaeli verisi kaydedildi: {sicaklik}°C, %{nem}")
    except Exception as e:
        print(f"[HATA] Arka plan veri çekme hatası: {e}")

scheduler = BackgroundScheduler()

@app.on_event("startup")
def startup():
    init_db()
    scheduler.add_job(veri_cek_ve_kaydet_gorevi, "interval", seconds=60)
    scheduler.start()

@app.on_event("shutdown")
def shutdown():
    scheduler.shutdown()

@app.post("/guncelle")
def elle_guncelle():
    veri_cek_ve_kaydet_gorevi()
    return {"durum": "Manuel tetikleme başarılı"}

@app.get("/analiz")
def hava_analizi():
    if not DB_PATH.exists():
        return {"mesaj": "Veritabanı henüz oluşmadı."}

    conn = sqlite3.connect(str(DB_PATH))
    df = pd.read_sql_query("SELECT sicaklik, nem, zaman FROM hava_durumu", conn)
    conn.close()

    if df.empty:
        return {"mesaj": "Henüz analiz edilecek veri yok."}

    return {
        "sehir": "Kocaeli",
        "toplam_olcum_sayisi": len(df),
        "sicaklik": {
            "ortalama": round(float(df["sicaklik"].mean()), 2),
            "en_dusuk": float(df["sicaklik"].min()),
            "en_yuksek": float(df["sicaklik"].max())
        },
        "nem": {
            "ortalama": round(float(df["nem"].mean()), 2),
            "en_dusuk": float(df["nem"].min()),
            "en_yuksek": float(df["nem"].max())
        }
    }

@app.get("/", response_class=HTMLResponse)
def anasayfa(request: Request):
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    # Grafikte soldan sağa kronolojik aksın diye son 20 kaydı çekip eskiden yeniye diziyoruz
    cur.execute("""
        SELECT sehir, sicaklik, nem, strftime('%H:%M:%S', zaman) as saat, zaman 
        FROM hava_durumu 
        ORDER BY id DESC LIMIT 20;
    """)
    kayitlar = [dict(r) for r in cur.fetchall()]
    conn.close()

    # Grafik için kronolojik (eskiden yeniye) sıralama
    grafik_kayitlar = list(reversed(kayitlar))
    grafik_zamanlar = [k["saat"] if k["saat"] else k["zaman"] for k in grafik_kayitlar]
    grafik_sicaklik = [k["sicaklik"] for k in grafik_kayitlar]
    grafik_nem = [k["nem"] for k in grafik_kayitlar]

    analiz_verisi = hava_analizi()
    if "sicaklik" not in analiz_verisi:
        analiz_verisi = None

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "request": request, 
            "kayitlar": kayitlar, 
            "analiz": analiz_verisi,
            "grafik_zamanlar": grafik_zamanlar,
            "grafik_sicaklik": grafik_sicaklik,
            "grafik_nem": grafik_nem
        }
    )