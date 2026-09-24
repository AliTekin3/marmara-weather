# -*- coding: utf-8 -*-
import sqlite3
import requests
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# Kocaeli koordinatlari
KOCAELI_LAT = 40.7654
KOCAELI_LON = 29.9408

def init_db():
    conn = sqlite3.connect("kocaeli_hava.db")
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

@app.on_event("startup")
def startup():
    init_db()

@app.post("/guncelle")
def veriyi_cek_ve_kaydet():
    url = f"https://api.open-meteo.com/v1/forecast?latitude={KOCAELI_LAT}&longitude={KOCAELI_LON}&current=temperature_2m,relative_humidity_2m"
    res = requests.get(url).json()
    
    sicaklik = res["current"]["temperature_2m"]
    nem = res["current"]["relative_humidity_2m"]

    conn = sqlite3.connect("kocaeli_hava.db")
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO hava_durumu (sehir, sicaklik, nem) VALUES (?, ?, ?);",
        ("Kocaeli", sicaklik, nem)
    )
    conn.commit()
    conn.close()

    return {"durum": "Kocaeli verisi kaydedildi", "sicaklik": sicaklik}

@app.get("/", response_class=HTMLResponse)
def anasayfa(request: Request):
    conn = sqlite3.connect("kocaeli_hava.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    cur.execute("SELECT sehir, sicaklik, nem, zaman FROM hava_durumu ORDER BY id DESC;")
    kayitlar = [dict(r) for r in cur.fetchall()]
    conn.close()

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"kayitlar": kayitlar}
    )