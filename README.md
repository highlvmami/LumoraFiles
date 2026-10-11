<div align="center">

# LumoraFiles

**Aynı Wi-Fi'deki telefonla bilgisayar arasında dosya aktaran ve telefonu bilgisayarın uzaktan kumandasına çeviren masaüstü uygulaması.**

Türkçe · [English](README.en.md)

<p>
  <img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/Flask-3-000000?logo=flask&logoColor=white" alt="Flask 3">
  <img src="https://img.shields.io/badge/Tkinter-GUI-FFD43B?logo=python&logoColor=black" alt="Tkinter">
  <img src="https://img.shields.io/badge/JavaScript-F7DF1E?logo=javascript&logoColor=black" alt="JavaScript">
  <img src="https://img.shields.io/badge/pynput-mss-6366F1" alt="pynput, mss">
  <img src="https://img.shields.io/badge/Windows-0078D4?logo=windows&logoColor=white" alt="Windows">
</p>

</div>

Bilgisayarda küçük bir pencere açılır: QR kod, adres ve PIN gösterir. Telefonla QR'ı okutursun, tarayıcıda bir sayfa açılır; uygulama kurmak gerekmez, internet de gerekmez. Oradan dosya gönderir, bilgisayardan dosya indirir, bilgisayarın ses ve sunumunu yönetir, fareyi ve klavyeyi kullanır, ekranını izlersin. Sunucu Python + Flask, pencere Tkinter, telefon sayfası çerçevesiz sade HTML/CSS/JS.

> Her şey yerel ağda kalır, hiçbir veri internete çıkmaz. Telefondan bilgisayarı yönetebildiğin için PIN'i kimseyle paylaşma ve bağlantı noktasını (8000) internete açma.

## Özellikler

### Dosya aktarımı
- **Telefondan bilgisayara:** birden fazla dosya seç, her dosya için ilerleme çubuğu görünür. Büyük dosyalar belleği şişirmeden diske akar.
- **Bilgisayardan telefona:** dosyayı pencereye sürükle-bırak (ya da "Dosya seç…"), telefondaki sayfada indirme listesinde belirir.
- Aynı adlı dosya ezilmez (`foto_1.jpg`); dosya adlarındaki `../` gibi yol hileleri temizlenir.

### Telefon kumandası
- **Medya ve ses:** oynat/durdur, sonraki/önceki, ses aç/kıs, sessiz.
- **Sunum:** ileri, geri, başlat (F5), karart, bitir.
- **Fare ve klavye:** tek parmakla fare, dokun = sol tık, iki parmakla dokun = sağ tık, iki parmakla kaydır = tekerlek. Türkçe karakterli metin yazma, Enter / ok tuşları / Esc gibi özel tuşlar.
- **Bilgisayar komutları:** kilitle, uyut, kapat, yeniden başlat. Kapat ve yeniden başlat telefonda onay ister, 30 saniye gecikir ve iptal edilebilir.
- **Programlar:** `komutlar.json` dosyasındaki listeden program aç (varsayılan: Hesap makinesi, Not Defteri, Dosya Gezgini).
- **Ekran izleme:** bilgisayar ekranını telefonda canlı gör, görüntüye dokunduğun noktaya bilgisayarda tıklanır.

### Güvenlik
- **PIN:** her açılışta rastgele 6 haneli PIN üretilir. PIN'i bilmeyen cihaz hiçbir sayfaya ve dosyaya ulaşamaz.
- **QR ile giriş:** QR kod PIN'i içerir, okutan telefon PIN yazmadan girer.
- **Deneme sınırı:** 5 yanlış denemede o cihaz 1 dakika kilitlenir.
- **Yeni PIN:** tek tıkla yeni PIN üretir ve bağlı bütün telefonların oturumunu kapatır.
- **Uzaktan kontrol düğmesi:** pencerede tek kutuyla kumanda ve ekran izleme kapatılır, dosya aktarımı çalışmaya devam eder.
- Telefon, `komutlar.json`'daki bir programın yalnızca **sıra numarasını** yollayabilir; komutun kendisini yollayamaz.

## Nasıl kullanılır

1. `LumoraFiles.bat` dosyasına çift tıkla. İlk açılışta gerekenleri kendisi kurar.
2. Açılan pencerede QR kod ve PIN görünür.
3. Telefonu bilgisayarla **aynı Wi-Fi'ye** bağla ve QR'ı okut. Sayfa açılır ve giriş otomatik yapılır.
4. Üstteki sekmelerden **Dosya**, **Kumanda** ya da **Ekran**'ı seç.

## Nasıl çalışır

- **Sunucu pencerenin içinde.** `masaustu.py` Flask sunucusunu arka plandaki bir iş parçacığında (thread) başlatır, ana iş parçacığı Tkinter penceresine kalır. Sunucu pencereye doğrudan dokunmaz; gelen dosyaların adlarını bir `queue.Queue`'ya bırakır, pencere yarım saniyede bir kuyruğa bakıp listesini günceller.
- **Yerel IP.** İçinden paket gönderilmeyen bir UDP soketi dış bir adrese "bağlanır"; işletim sistemi hangi ağ kartını seçtiyse onun adresi bilgisayarın yerel IP'sidir. Sunucu `0.0.0.0` üzerinde dinler, yoksa telefon bağlanamazdı.
- **İlerleme çubuğu.** Her dosya ayrı bir `XMLHttpRequest` ile yollanır; `fetch` yükleme ilerlemesini vermediği için `upload.onprogress` kullanılır.
- **Tuş ve fare.** `pynput` ile gerçek giriş olayları üretilir; medya tuşları, sunum tuşları ve Unicode metin aynı yoldan gider. Dokunmatik yüzeyde hareketler sunucuya her harekette değil 30 ms'de bir toplu gönderilir.
- **Ekran izleme.** `mss` ana ekranı yakalar, Pillow küçültüp JPEG yapar. Telefon bir kare inince bir sonrakini ister, bu yüzden hız ağa göre kendiliğinden ayarlanır. Kare önce belleğe indirilip sonra yerine konur, görüntü yanıp sönmez. Dokunulan nokta ekranın **oranı** olarak yollanır, bu yüzden ekran çözünürlüğünden bağımsız çalışır.
- **PIN ve oturum.** Doğru PIN'e rastgele bir oturum anahtarı verilir, çerez olarak saklanır. Her istek (dosya, kumanda, ekran) bu anahtarı kontrol eder. PIN karşılaştırması sabit sürelidir.

## Teknolojiler

| Parça | Teknoloji |
|---|---|
| Sunucu | Python 3.10+, Flask |
| Masaüstü penceresi | Tkinter, `tkinterdnd2` (sürükle-bırak) |
| Telefon sayfası | HTML, CSS, JavaScript (çerçevesiz) |
| Tuş ve fare | `pynput` |
| Ekran görüntüsü | `mss`, Pillow |
| QR kod | `qrcode` |

## Klasör yapısı

| Yol | Ne işe yarar |
|---|---|
| `main.py` | Flask sunucusu: dosya aktarımı, PIN girişi, yerel IP bulma |
| `uzak.py` | Uzaktan kontrol: medya, sunum, fare, klavye, komutlar, ekran görüntüsü |
| `masaustu.py` | Tkinter penceresi (QR, PIN, dosya listeleri, izin kutusu) |
| `templates/index.html` | Telefon sayfası (Dosya / Kumanda / Ekran sekmeleri) |
| `templates/giris.html` | PIN giriş sayfası |
| `komutlar.json` | Telefondan açılabilecek programlar (ilk açılışta oluşur) |
| `LumoraFiles.bat` | Windows'ta çift tıkla başlatıcı, kurulumu da yapar |
| `alinanlar/` | Telefondan gelen dosyalar |
| `paylasilan/` | Telefona hazırlanan dosyalar |

## Çalıştırma

Gereksinimler: Python 3.10+ ([python.org](https://www.python.org/downloads/), kurulumda **"Add python.exe to PATH"** işaretli olsun). Tkinter python.org kurulumuyla birlikte gelir.

**Windows:** `LumoraFiles.bat` dosyasına çift tıkla.

**Elle:**

```bash
python -m venv venv
venv\Scripts\activate          # macOS / Linux: source venv/bin/activate
pip install -r requirements.txt
python masaustu.py             # pencere ile
python main.py                 # sadece sunucu, QR kodu terminale basar
```

## Ayarlar

| Ayar | Açıklama |
|---|---|
| `PORT` (`main.py`) | Sunucu portu, varsayılan 8000 |
| `DENEME_SINIRI`, `KILIT_SURESI` (`main.py`) | PIN'de kaç yanlışta, kaç saniye kilitleneceği (5 deneme, 60 sn) |
| `komutlar.json` | `[{"ad": "Hesap makinesi", "komut": "calc"}]` biçiminde program listesi |
| `LUMORA_KURU=1` (ortam değişkeni) | Gerçek tuş/komut yerine sadece kaydeder; test için |

## Sorun giderme

- Telefon ve bilgisayar **aynı Wi-Fi'de** olmalı. Misafir ağları genelde cihazları birbirinden ayırır.
- Windows ilk açılışta güvenlik duvarı izni ister: **Özel ağlar** için izin ver.
- QR okunmazsa telefonda adresi elle yaz (pencerede yazan `http://192.168…:8000`) ve PIN'i gir.
- PIN her açılışta değişir; uygulamayı yeniden açtıysan QR'ı yeniden okut.
- Sistem komutları (kilitle, uyut, kapat) şimdilik yalnızca Windows'ta çalışır. Dosya aktarımı diğer sistemlerde de çalışır.
