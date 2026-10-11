"""LumoraFiles - uzaktan kontrol.

Telefondan bilgisayara: medya ve sunum tuşları, fare ve klavye, bilgisayar
komutları (kilitle, uyut, kapat…) ve ekran görüntüsü.

Bütün adresler /uzak/ altındadır. PIN girişi main.py'de yapılır; bu dosyaya
sadece PIN'i bilen telefonlar ulaşabilir. Pencerede "Uzaktan kontrole izin ver"
kutusu kapatılırsa buradaki her adres 403 döner.
"""

import io
import json
import os
import queue
import subprocess
import sys
import threading
from pathlib import Path

from flask import Blueprint, jsonify, request, send_file

TEMEL = Path(__file__).parent
KOMUT_DOSYASI = TEMEL / "komutlar.json"

# LUMORA_KURU=1 ise gerçek tuş basmak/komut çalıştırmak yerine sadece kaydeder.
# Testlerde bilgisayarı gerçekten kapatmamak için var.
KURU = os.environ.get("LUMORA_KURU") == "1"

if sys.platform == "win32":
    # Ekran %125/%150 büyütmeliyken fare koordinatları ile ekran görüntüsü aynı
    # ölçüde kalsın diye süreç DPI'a duyarlı yapılır (pencere açılmadan önce).
    try:
        import ctypes
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


class Durum:
    izin = True                 # pencereden açılıp kapatılır
    olaylar = queue.Queue()     # pencere "telefon şunu yaptı" diye buradan okur
    kuru_kayit = []             # sadece test için


def _olay(metin):
    Durum.olaylar.put(metin)


# --- tuş ve fare ------------------------------------------------------------

_kontrolcu = {}
_kilit = threading.Lock()


def _kontrol():
    """pynput'u ilk kullanıldığında yükler (uygulama açılışı yavaşlamasın)."""
    with _kilit:
        if not _kontrolcu:
            from pynput import keyboard, mouse
            _kontrolcu["k"] = keyboard.Controller()
            _kontrolcu["f"] = mouse.Controller()
            _kontrolcu["Key"] = keyboard.Key
            _kontrolcu["Button"] = mouse.Button
    return _kontrolcu


def _bas(tus):
    """Tek bir tuşa basıp bırakır. "media_volume_up" gibi adlar ya da tek harf."""
    if KURU:
        Durum.kuru_kayit.append(("tus", tus))
        return
    c = _kontrol()
    hedef = tus if len(tus) == 1 else getattr(c["Key"], tus)
    c["k"].press(hedef)
    c["k"].release(hedef)


MEDYA = {
    "oynat": "media_play_pause", "sonraki": "media_next", "onceki": "media_previous",
    "ses_art": "media_volume_up", "ses_azalt": "media_volume_down",
    "sessiz": "media_volume_mute",
}
MEDYA_ADI = {
    "oynat": "Oynat/durdur", "sonraki": "Sonraki parça", "onceki": "Önceki parça",
    "ses_art": "Ses aç", "ses_azalt": "Ses kıs", "sessiz": "Sessiz",
}
SUNUM = {"ileri": "right", "geri": "left", "baslat": "f5", "bitir": "esc", "karart": "b"}
SUNUM_ADI = {"ileri": "Sunum: ileri", "geri": "Sunum: geri", "baslat": "Sunum: başlat",
             "bitir": "Sunum: bitir", "karart": "Sunum: ekranı karart"}
TUSLAR = {"enter", "backspace", "tab", "esc", "up", "down", "left", "right",
          "space", "delete", "home", "end", "page_up", "page_down"}


# --- bilgisayar komutları ---------------------------------------------------

VARSAYILAN_KOMUTLAR = [
    {"ad": "Hesap makinesi", "komut": "calc"},
    {"ad": "Not Defteri", "komut": "notepad"},
    {"ad": "Dosya Gezgini", "komut": "explorer"},
]

SISTEM_KOMUTLARI = {
    "kilitle": ["rundll32.exe", "user32.dll,LockWorkStation"],
    "uyut": ["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"],
    "kapat": ["shutdown", "/s", "/t", "30"],
    "yeniden_baslat": ["shutdown", "/r", "/t", "30"],
    "iptal": ["shutdown", "/a"],
}
SISTEM_ADI = {"kilitle": "Bilgisayar kilitlendi", "uyut": "Bilgisayar uyutuldu",
              "kapat": "Kapatma başladı (30 sn)", "yeniden_baslat": "Yeniden başlatma başladı (30 sn)",
              "iptal": "Kapatma iptal edildi"}


def komutlari_oku():
    """Telefonda görünecek programlar. komutlar.json'u kendin düzenleyebilirsin.

    Telefon sadece listedeki bir adın SIRA NUMARASINI yollar; komutun kendisini
    yollayamaz. Böylece telefon bilgisayarda keyfi bir şey çalıştıramaz.
    """
    if not KOMUT_DOSYASI.exists():
        KOMUT_DOSYASI.write_text(
            json.dumps(VARSAYILAN_KOMUTLAR, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        liste = json.loads(KOMUT_DOSYASI.read_text(encoding="utf-8"))
        return [k for k in liste if isinstance(k, dict) and k.get("ad") and k.get("komut")]
    except (OSError, ValueError):
        return list(VARSAYILAN_KOMUTLAR)


# --- ekran görüntüsü --------------------------------------------------------

def ekran_jpeg(genislik=1280, kalite=55):
    """Ana ekranın JPEG görüntüsü ve ekranın gerçek boyutu."""
    import mss
    from PIL import Image
    with mss.mss() as m:
        mon = m.monitors[1]  # 1 = ana ekran, 0 = bütün ekranların birleşimi
        shot = m.grab(mon)
        img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
    if img.width > genislik:
        img = img.resize((genislik, round(img.height * genislik / img.width)), Image.BILINEAR)
    tampon = io.BytesIO()
    img.save(tampon, "JPEG", quality=kalite)
    return tampon.getvalue(), mon


# --- adresler -----------------------------------------------------------------

uzak_bp = Blueprint("uzak", __name__, url_prefix="/uzak")


@uzak_bp.before_request
def izin_kontrol():
    if not Durum.izin:
        return jsonify(ok=False, hata="Uzaktan kontrol bilgisayarda kapalı"), 403


def _veri():
    return request.get_json(silent=True) or {}


def _sayi(deger, sinir):
    try:
        return max(-sinir, min(sinir, int(round(float(deger)))))
    except (TypeError, ValueError):
        return 0


def _hata(metin, kod=400):
    return jsonify(ok=False, hata=metin), kod


@uzak_bp.get("/bilgi")
def bilgi():
    return jsonify(ok=True, izin=Durum.izin,
                   komutlar=[k["ad"] for k in komutlari_oku()],
                   windows=sys.platform == "win32")


@uzak_bp.post("/medya")
def medya():
    eylem = _veri().get("eylem")
    if eylem not in MEDYA:
        return _hata("Bilinmeyen medya eylemi")
    _bas(MEDYA[eylem])
    _olay("📱 " + MEDYA_ADI[eylem])
    return jsonify(ok=True)


@uzak_bp.post("/sunum")
def sunum():
    eylem = _veri().get("eylem")
    if eylem not in SUNUM:
        return _hata("Bilinmeyen sunum eylemi")
    _bas(SUNUM[eylem])
    _olay("📱 " + SUNUM_ADI[eylem])
    return jsonify(ok=True)


@uzak_bp.post("/fare")
def fare():
    v = _veri()
    dx, dy = _sayi(v.get("dx"), 400), _sayi(v.get("dy"), 400)
    if KURU:
        Durum.kuru_kayit.append(("fare", dx, dy))
    else:
        _kontrol()["f"].move(dx, dy)
    return jsonify(ok=True)


@uzak_bp.post("/kaydir")
def kaydir():
    dy = _sayi(_veri().get("dy"), 30)
    if KURU:
        Durum.kuru_kayit.append(("kaydir", dy))
    elif dy:
        _kontrol()["f"].scroll(0, dy)  # + yukarı, - aşağı
    return jsonify(ok=True)


@uzak_bp.post("/tik")
def tik():
    dugme = _veri().get("dugme")
    if dugme not in ("sol", "sag", "cift"):
        return _hata("Bilinmeyen düğme")
    if KURU:
        Durum.kuru_kayit.append(("tik", dugme))
    else:
        c = _kontrol()
        c["f"].click(c["Button"].right if dugme == "sag" else c["Button"].left,
                     2 if dugme == "cift" else 1)
    return jsonify(ok=True)


@uzak_bp.post("/tikla_mutlak")
def tikla_mutlak():
    """Ekran görüntüsüne dokunulan yere tıklar. x ve y 0 ile 1 arası orandır."""
    v = _veri()
    try:
        ox, oy = float(v["x"]), float(v["y"])
    except (KeyError, TypeError, ValueError):
        return _hata("Konum gerekli")
    if not (0 <= ox <= 1 and 0 <= oy <= 1):
        return _hata("Konum ekranın dışında")
    if KURU:
        Durum.kuru_kayit.append(("tikla_mutlak", round(ox, 3), round(oy, 3)))
        return jsonify(ok=True)
    import mss
    with mss.mss() as m:
        mon = m.monitors[1]
    c = _kontrol()
    c["f"].position = (mon["left"] + round(ox * (mon["width"] - 1)),
                       mon["top"] + round(oy * (mon["height"] - 1)))
    c["f"].click(c["Button"].right if v.get("dugme") == "sag" else c["Button"].left, 1)
    return jsonify(ok=True)


@uzak_bp.post("/yaz")
def yaz():
    metin = str(_veri().get("metin", ""))[:500]
    if not metin:
        return _hata("Yazılacak metin yok")
    if KURU:
        Durum.kuru_kayit.append(("yaz", metin))
    else:
        _kontrol()["k"].type(metin)
    _olay(f"📱 Yazıldı: {metin[:30]}")
    return jsonify(ok=True)


@uzak_bp.post("/tus")
def tus():
    ad = _veri().get("tus")
    if ad not in TUSLAR:
        return _hata("Bilinmeyen tuş")
    _bas(ad)
    return jsonify(ok=True)


def _calistir(komut, kabuk=False):
    if KURU:
        Durum.kuru_kayit.append(("komut", komut))
        return
    subprocess.Popen(komut, shell=kabuk, stdin=subprocess.DEVNULL,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


@uzak_bp.post("/komut")
def komut():
    v = _veri()
    sistem = v.get("sistem")
    if sistem is not None:
        if sistem not in SISTEM_KOMUTLARI:
            return _hata("Bilinmeyen komut")
        if sys.platform != "win32" and not KURU:
            return _hata("Bu komut şimdilik sadece Windows'ta çalışıyor", 501)
        _calistir(SISTEM_KOMUTLARI[sistem])
        _olay("📱 " + SISTEM_ADI[sistem])
        return jsonify(ok=True)
    liste = komutlari_oku()
    try:
        secilen = liste[int(v.get("sira"))]
    except (TypeError, ValueError, IndexError):
        return _hata("Bilinmeyen program")
    _calistir(secilen["komut"], kabuk=True)  # komut, senin komutlar.json dosyandan gelir
    _olay(f"📱 Açıldı: {secilen['ad']}")
    return jsonify(ok=True)


@uzak_bp.get("/ekran.jpg")
def ekran():
    try:
        veri, _ = ekran_jpeg()
    except Exception as e:  # ekran yakalanamazsa (ör. kilit ekranı) telefona hata dön
        return _hata(f"Ekran alınamadı: {e}", 500)
    yanit = send_file(io.BytesIO(veri), mimetype="image/jpeg")
    yanit.headers["Cache-Control"] = "no-store"
    return yanit
