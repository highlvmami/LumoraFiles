"""LumoraFiles - sunucu: telefondan bilgisayara ve bilgisayardan telefona dosya."""

import hmac
import queue
import secrets
import socket
import time
from pathlib import Path

import qrcode
from flask import (Flask, jsonify, make_response, redirect, render_template,
                   request, send_from_directory, url_for)

from uzak import uzak_bp

PORT = 8000
TEMEL = Path(__file__).parent
KLASOR = TEMEL / "alinanlar"        # telefondan gelenler
PAYLASILAN = TEMEL / "paylasilan"   # bilgisayardan telefona hazırlananlar
KLASOR.mkdir(exist_ok=True)
PAYLASILAN.mkdir(exist_ok=True)

app = Flask(__name__)
app.register_blueprint(uzak_bp)

# Yeni gelen her dosyanın adı buraya atılır. Masaüstü penceresi bu kuyruğu
# dinleyip listesini günceller. Kuyruk, iki iş parçacığı (thread) arasında
# güvenle veri taşımanın en basit yoludur.
alinanlar_kuyrugu = queue.Queue()


# --- PIN girişi -------------------------------------------------------------
# Aynı Wi-Fi'deki herkes adresi bulabilir. Bu yüzden her açılışta rastgele bir
# PIN üretilir; PIN'i bilmeyen cihaz hiçbir sayfaya ve dosyaya ulaşamaz.
# QR kodu PIN'i içerir: okutan telefon otomatik giriş yapar.

CEREZ = "lumora_oturum"
DENEME_SINIRI = 5       # bu kadar yanlışta
KILIT_SURESI = 60       # saniye boyunca o cihaz denemeden men edilir


class Kimlik:
    pin = ""
    oturumlar = set()   # PIN'i doğru giren tarayıcıların gizli anahtarları
    hatalar = {}        # IP -> yanlış deneme zamanları


def pin_yenile():
    """Yeni PIN üretir ve bağlı bütün telefonların oturumunu kapatır."""
    Kimlik.pin = f"{secrets.randbelow(10**6):06d}"
    Kimlik.oturumlar.clear()
    Kimlik.hatalar.clear()
    return Kimlik.pin


pin_yenile()


def pin_dene(ip, pin):
    """"ok", "yanlis" ya da "kilitli" döner."""
    simdi = time.time()
    son = [t for t in Kimlik.hatalar.get(ip, []) if simdi - t < KILIT_SURESI]
    Kimlik.hatalar[ip] = son
    if len(son) >= DENEME_SINIRI:
        return "kilitli"
    if hmac.compare_digest(pin.strip().encode(), Kimlik.pin.encode()):
        Kimlik.hatalar.pop(ip, None)
        return "ok"
    son.append(simdi)
    return "yanlis"


def oturum_ac():
    anahtar = secrets.token_urlsafe(32)
    Kimlik.oturumlar.add(anahtar)
    yanit = make_response(redirect(url_for("ana_sayfa")))
    yanit.set_cookie(CEREZ, anahtar, httponly=True, samesite="Lax", max_age=7 * 24 * 3600)
    return yanit


@app.before_request
def giris_kontrol():
    if request.endpoint == "giris":
        return None
    if request.cookies.get(CEREZ) in Kimlik.oturumlar:
        return None
    if request.method == "GET" and request.path == "/":
        return redirect(url_for("giris"))
    return jsonify(ok=False, hata="PIN gerekli"), 401


@app.route("/giris", methods=["GET", "POST"])
def giris():
    pin = request.form.get("pin") if request.method == "POST" else request.args.get("pin")
    if pin is None:
        return render_template("giris.html", hata=None)
    sonuc = pin_dene(request.remote_addr, pin)
    if sonuc == "ok":
        return oturum_ac()
    if sonuc == "kilitli":
        return render_template("giris.html", hata=f"Çok fazla yanlış deneme. {KILIT_SURESI} saniye bekle."), 429
    return render_template("giris.html", hata="PIN yanlış"), 401


def yerel_ip_bul():
    """Bilgisayarın yerel ağdaki IP adresini bulur (ör. 192.168.1.34).

    Dışarıdaki bir adrese UDP soketi "bağlıyoruz". UDP'de connect hiçbir
    paket göndermez; işletim sistemi sadece hangi ağ kartından çıkacağını
    seçer. O kartın adresi de bizim yerel IP'mizdir.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def guvenli_yol(dosya_adi, klasor=KLASOR):
    """Gelen dosya adını temizler ve var olan dosyanın üzerine yazmaz.

    "../../windows/x.exe" gibi bir ad gelirse sadece "x.exe" kısmını alırız,
    böylece kimse hedef klasörün dışına dosya yazamaz.
    """
    ad = dosya_adi.replace("\\", "/").split("/")[-1].strip()
    if ad in ("", ".", ".."):
        ad = "dosya"
    yol = klasor / ad
    sayac = 1
    while yol.exists():
        yol = klasor / f"{Path(ad).stem}_{sayac}{Path(ad).suffix}"
        sayac += 1
    return yol


def paylasilanlari_listele():
    """Telefona hazır dosyalar: [{"ad": ..., "boyut": bayt}, ...] (yeniden eskiye)."""
    dosyalar = [d for d in PAYLASILAN.iterdir() if d.is_file()]
    dosyalar.sort(key=lambda d: d.stat().st_mtime, reverse=True)
    return [{"ad": d.name, "boyut": d.stat().st_size} for d in dosyalar]


@app.get("/")
def ana_sayfa():
    return render_template("index.html")


@app.post("/yukle")
def yukle():
    """Tarayıcı her dosyayı ayrı bir istekle yollar; cevap JSON'dur."""
    dosya = request.files.get("dosya")
    if not dosya or not dosya.filename:
        return jsonify(ok=False, hata="Dosya seçilmedi"), 400
    yol = guvenli_yol(dosya.filename)
    dosya.save(yol)
    print(f"📥 Alındı: {yol.name} ({request.remote_addr})")
    alinanlar_kuyrugu.put(yol.name)
    return jsonify(ok=True, ad=yol.name)


@app.get("/liste")
def liste():
    """Telefondaki sayfa bunu birkaç saniyede bir sorar."""
    return jsonify(paylasilanlari_listele())


@app.get("/indir/<path:ad>")
def indir(ad):
    # send_from_directory, ad ile klasörün dışına çıkılmasını kendisi engeller.
    return send_from_directory(PAYLASILAN, ad, as_attachment=True)


if __name__ == "__main__":
    adres = f"http://{yerel_ip_bul()}:{PORT}"
    qr = qrcode.QRCode(border=1)
    qr.add_data(f"{adres}/giris?pin={Kimlik.pin}")
    qr.print_ascii(invert=True)
    print(f"\n📱 Telefonla QR'ı okut ya da tarayıcıya yaz: {adres}")
    print(f"🔑 PIN: {Kimlik.pin}")
    print(f"📂 Gelen dosyalar: {KLASOR}")
    print(f"📤 Telefona hazır dosyalar: {PAYLASILAN}\n")
    # 0.0.0.0 = "bütün ağ kartlarından gelen bağlantıları kabul et".
    # 127.0.0.1 yazsaydık sadece bu bilgisayar bağlanabilirdi, telefon değil.
    app.run(host="0.0.0.0", port=PORT, threaded=True)
