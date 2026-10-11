"""LumoraFiles - masaüstü penceresi.

Terminal yerine bir pencere açar: QR kodu, adresi, gelen dosyaları gösterir
ve telefona dosya göndermeni sağlar. Flask sunucusu arka planda ayrı bir iş
parçacığında (thread) çalışır, çünkü hem pencere hem sunucu "sonsuz döngü"
ister ve aynı anda tek döngü dönebilir.
"""

import os
import shutil
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog

import qrcode

from main import (KLASOR, PAYLASILAN, PORT, Kimlik, alinanlar_kuyrugu, app,
                  guvenli_yol, paylasilanlari_listele, pin_yenile, yerel_ip_bul)
from uzak import Durum

# Sürükle-bırak için tkinterdnd2 gerekir. Kurulu değilse pencere yine açılır,
# sadece "Dosya seç" butonu kalır.
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    PencereTabani = TkinterDnD.Tk
except Exception:
    DND_FILES = None
    PencereTabani = tk.Tk

ARKA_PLAN = "#0f172a"
KART = "#1e293b"
YAZI = "#e2e8f0"
SOLUK = "#94a3b8"
VURGU = "#6366f1"


def sunucuyu_baslat():
    # daemon=True: pencere kapanınca bu thread de kendiliğinden kapanır.
    threading.Thread(
        target=lambda: app.run(host="0.0.0.0", port=PORT, threaded=True),
        daemon=True,
    ).start()


def ac(yol):
    """Dosyayı ya da klasörü işletim sisteminin varsayılan programıyla açar."""
    if sys.platform == "win32":
        os.startfile(yol)
    elif sys.platform == "darwin":
        subprocess.run(["open", str(yol)])
    else:
        subprocess.run(["xdg-open", str(yol)])


def boyut_yaz(bayt):
    for birim in ("B", "KB", "MB", "GB"):
        if bayt < 1024 or birim == "GB":
            return f"{bayt:.0f} {birim}" if birim == "B" else f"{bayt:.1f} {birim}"
        bayt /= 1024


def qr_ciz(tuval, metin, kare=6):
    """QR kodu resim dosyası olmadan, küçük siyah karelerle çizer."""
    qr = qrcode.QRCode(border=2)
    qr.add_data(metin)
    matris = qr.get_matrix()  # True = siyah kare, False = beyaz kare
    boyut = len(matris) * kare
    tuval.config(width=boyut, height=boyut)
    tuval.create_rectangle(0, 0, boyut, boyut, fill="white", outline="")
    for y, satir in enumerate(matris):
        for x, siyah in enumerate(satir):
            if siyah:
                tuval.create_rectangle(
                    x * kare, y * kare, (x + 1) * kare, (y + 1) * kare,
                    fill="black", outline="",
                )


def baslik(ust, metin):
    tk.Label(ust, text=metin, bg=ARKA_PLAN, fg=SOLUK).pack(anchor="w", pady=(10, 4))


def liste_kutusu(ust, yukseklik):
    return tk.Listbox(ust, height=yukseklik, bg=KART, fg=YAZI, relief="flat",
                      selectbackground=VURGU, font=("Segoe UI", 11),
                      activestyle="none")


class Pencere(PencereTabani):
    def __init__(self, adres):
        super().__init__()
        self.title("LumoraFiles")
        self.configure(bg=ARKA_PLAN, padx=24, pady=16)
        self.resizable(False, False)

        self.adres = adres
        sol = tk.Frame(self, bg=ARKA_PLAN)
        sol.grid(row=0, column=0, sticky="n", padx=(0, 24))
        sag = tk.Frame(self, bg=ARKA_PLAN, width=330)
        sag.grid(row=0, column=1, sticky="n")

        # --- sol sütun: QR, adres, PIN, izin ---
        tk.Label(sol, text="✨ LumoraFiles", font=("Segoe UI", 20, "bold"),
                 bg=ARKA_PLAN, fg=YAZI).pack()
        tk.Label(sol, text="Telefonunla QR'ı okut, bağlan",
                 bg=ARKA_PLAN, fg=SOLUK).pack(pady=(0, 10))

        self.tuval = tk.Canvas(sol, highlightthickness=0)
        self.tuval.pack()

        satir = tk.Frame(sol, bg=ARKA_PLAN)
        satir.pack(pady=(8, 0))
        tk.Label(satir, text=adres, font=("Consolas", 11),
                 bg=ARKA_PLAN, fg=YAZI).pack(side="left")
        tk.Button(satir, text="Kopyala", command=lambda: self.kopyala(adres),
                  bg=KART, fg=YAZI, relief="flat", padx=8).pack(side="left", padx=8)

        pinsatir = tk.Frame(sol, bg=ARKA_PLAN)
        pinsatir.pack(pady=(10, 0))
        tk.Label(pinsatir, text="PIN", bg=ARKA_PLAN, fg=SOLUK).pack(side="left")
        self.pin_etiketi = tk.Label(pinsatir, font=("Consolas", 18, "bold"),
                                    bg=ARKA_PLAN, fg=YAZI)
        self.pin_etiketi.pack(side="left", padx=8)
        tk.Button(pinsatir, text="Yeni PIN", command=self.yeni_pin,
                  bg=KART, fg=YAZI, relief="flat", padx=8).pack(side="left")

        self.izin = tk.BooleanVar(value=Durum.izin)
        tk.Checkbutton(sol, text="📱 Telefon bilgisayarı uzaktan kontrol edebilsin",
                       variable=self.izin, command=self.izin_degisti, justify="left",
                       bg=ARKA_PLAN, fg=YAZI, selectcolor=KART, activebackground=ARKA_PLAN,
                       activeforeground=YAZI, wraplength=300).pack(pady=(12, 0), anchor="w")
        tk.Label(sol, text="medya, fare, klavye, komutlar, ekran izleme",
                 bg=ARKA_PLAN, fg=SOLUK).pack(anchor="w", padx=24)

        self.durum = tk.Label(sol, text="Hazır, telefon bekleniyor…", wraplength=300,
                              bg=ARKA_PLAN, fg=SOLUK)
        self.durum.pack(pady=(10, 0))

        self.qr_yenile()

        # --- sağ sütun: dosyalar ---
        self.sag = sag
        ust = sag
        baslik(ust, "📥 Telefondan gelenler (açmak için çift tıkla)")
        self.liste = liste_kutusu(ust, 5)
        self.liste.pack(fill="x")
        self.liste.bind("<Double-Button-1>", self.gelen_ac)
        tk.Button(ust, text="📂 Gelenler klasörünü aç", command=lambda: ac(KLASOR),
                  bg=KART, fg=YAZI, relief="flat", pady=4).pack(fill="x", pady=(6, 0))

        baslik(ust, "📤 Telefona gönder")
        ipucu = ("Dosyaları buraya sürükle-bırak" if DND_FILES
                 else "Dosya seç butonunu kullan")
        self.birakma = tk.Label(ust, text=f"⬇  {ipucu}", bg=KART, fg=SOLUK,
                                height=3, relief="flat")
        self.birakma.pack(fill="x")
        if DND_FILES:
            self.birakma.drop_target_register(DND_FILES)
            self.birakma.dnd_bind("<<Drop>>", self.birakildi)
        tk.Button(ust, text="Dosya seç…", command=self.dosya_sec,
                  bg=VURGU, fg="white", relief="flat", pady=6,
                  font=("Segoe UI", 11, "bold")).pack(fill="x", pady=(6, 0))

        self.paylasilan = liste_kutusu(ust, 4)
        self.paylasilan.pack(fill="x", pady=(8, 0))
        self.paylasilan.bind("<Double-Button-1>", self.paylasilan_ac)
        alt = tk.Frame(ust, bg=ARKA_PLAN)
        alt.pack(fill="x", pady=(6, 0))
        tk.Button(alt, text="Seçileni kaldır", command=self.kaldir,
                  bg=KART, fg=YAZI, relief="flat", pady=4).pack(side="left", expand=True, fill="x")
        tk.Button(alt, text="Hepsini kaldır", command=lambda: self.kaldir(hepsi=True),
                  bg=KART, fg=YAZI, relief="flat", pady=4).pack(side="left", expand=True, fill="x", padx=(6, 0))

        self.paylasilan_adlari = []
        self.paylasilanlari_yenile()
        self.kuyrugu_dinle()

    # --- PIN, QR ve izin ---
    def qr_yenile(self):
        self.pin_etiketi.config(text=Kimlik.pin)
        self.tuval.delete("all")
        # QR, PIN'i de içerir: okutan telefon PIN yazmadan giriş yapar.
        qr_ciz(self.tuval, f"{self.adres}/giris?pin={Kimlik.pin}")

    def yeni_pin(self):
        pin_yenile()
        self.qr_yenile()
        self.durum.config(text="Yeni PIN üretildi, bağlı telefonlar çıkış yaptı")

    def izin_degisti(self):
        Durum.izin = self.izin.get()
        self.durum.config(text="Uzaktan kontrol açıldı" if Durum.izin
                          else "Uzaktan kontrol kapatıldı")

    # --- genel ---
    def kopyala(self, metin):
        self.clipboard_clear()
        self.clipboard_append(metin)
        self.durum.config(text="Adres panoya kopyalandı")

    # --- telefondan gelenler ---
    def gelen_ac(self, _olay):
        secim = self.liste.curselection()
        if secim:
            ac(KLASOR / self.liste.get(secim[0]))

    def kuyrugu_dinle(self):
        # Tkinter'a sadece kendi thread'inden dokunulabilir. Bu yüzden sunucu
        # pencereyi doğrudan değiştirmez; biz yarım saniyede bir kuyruğa bakarız.
        while not alinanlar_kuyrugu.empty():
            ad = alinanlar_kuyrugu.get()
            self.liste.insert(0, ad)
            self.durum.config(text=f"📥 Alındı: {ad}")
            self.bell()
        while not Durum.olaylar.empty():
            self.durum.config(text=Durum.olaylar.get())
        self.after(500, self.kuyrugu_dinle)

    # --- telefona gönderilecekler ---
    def dosya_sec(self):
        yollar = filedialog.askopenfilenames(title="Telefona gönderilecek dosyalar")
        self.paylas(yollar)

    def birakildi(self, olay):
        # Boşluklu yollar süslü parantezle gelir; splitlist bunları doğru ayırır.
        self.paylas(self.tk.splitlist(olay.data))

    def paylas(self, yollar):
        sayi = 0
        for yol in yollar:
            if not os.path.isfile(yol):  # klasörleri atla
                continue
            self.durum.config(text=f"Kopyalanıyor: {os.path.basename(yol)}…")
            self.update_idletasks()
            shutil.copy2(yol, guvenli_yol(os.path.basename(yol), PAYLASILAN))
            sayi += 1
        self.paylasilanlari_yenile()
        if sayi:
            self.durum.config(text=f"📤 {sayi} dosya telefona hazır")
        elif yollar:
            self.durum.config(text="Klasörler gönderilemez, dosya seç")

    def paylasilanlari_yenile(self):
        dosyalar = paylasilanlari_listele()
        self.paylasilan_adlari = [d["ad"] for d in dosyalar]
        self.paylasilan.delete(0, "end")
        for d in dosyalar:
            self.paylasilan.insert("end", f'{d["ad"]}  ({boyut_yaz(d["boyut"])})')

    def paylasilan_ac(self, _olay):
        secim = self.paylasilan.curselection()
        if secim:
            ac(PAYLASILAN / self.paylasilan_adlari[secim[0]])

    def kaldir(self, hepsi=False):
        # Paylaşımdan kaldırınca kopya silinir; senin asıl dosyana dokunulmaz.
        if hepsi:
            adlar = list(self.paylasilan_adlari)
        else:
            adlar = [self.paylasilan_adlari[i] for i in self.paylasilan.curselection()]
        for ad in adlar:
            (PAYLASILAN / ad).unlink(missing_ok=True)
        self.paylasilanlari_yenile()
        if adlar:
            self.durum.config(text=f"{len(adlar)} dosya paylaşımdan kaldırıldı")


if __name__ == "__main__":
    sunucuyu_baslat()
    Pencere(f"http://{yerel_ip_bul()}:{PORT}").mainloop()
