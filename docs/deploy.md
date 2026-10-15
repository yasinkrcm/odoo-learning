# 🚀 Canlıya Alma Rehberi (VPS + Docker + Caddy HTTPS)

Hedef: `https://odoo.yasinkaracam.com` üzerinde, geliştirme verisiyle çalışan kalıcı bir Odoo 19 kurulumu.

```
Tarayıcı → Caddy (Let's Encrypt TLS) → odoo (workers=1, proxy_mode=True) → postgres (host'a açık değil)
```

---

## 0. Ön Koşullar

- VPS: Ubuntu 22.04/24.04, en az **2 GB RAM + 20 GB disk**
- DNS: `odoo.yasinkaracam.com` için **A record → sunucu IP**; doğrula: `dig +short odoo.yasinkaracam.com`
- Güvenlik duvarında 80/443 açık: `sudo ufw allow 80,443/tcp`

## 1. Sunucu Hazırlığı

```bash
sudo apt update && sudo apt upgrade -y

# Docker kurulumu (resmi script)
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER && newgrp docker
docker --version

# Dosya yapısı
sudo mkdir -p /opt/odoo && cd /opt/odoo
```

Repo'daki dosyaları sunucuya taşı:

```bash
# local (Mac) tarafında:
git clone https://github.com/yasinkrcm/odoo-learning.git /tmp/odoo-learning
rsync -av --delete /tmp/odoo-learning/addons/ user@<sunucu-ip>:/opt/odoo/addons/
rsync -av /tmp/odoo-learning/deploy/ user@<sunucu-ip>:/opt/odoo/
```

> **Neden `deploy/` klasörü?** Repo kökündeki `docker-compose.yml` geliştirme içindir: varsayılan `odoo/odoo` şifreleri, TLS yok ve DB host'a açık. Canlıda **`/opt/odoo/docker-compose.yml`** (deploy klasöründeki) kullanılır — DB host'a hiç açılmaz, Caddy ters proxy + otomatik sertifika sağlar.

## 2. Secrets — bizzat sunucuda üret

```bash
cd /opt/odoo
cp deploy/.env.example .env
openssl rand -hex 24        # çıktıyı kopyala → POSTGRES_PASSWORD'e yaz
nano .env
```

`.env` içeriği:

```ini
POSTGRES_USER=odoo
POSTGRES_PASSWORD=<openssl çıktısı>
SITE_DOMAIN=odoo.yasinkaracam.com
```

`odoo.conf` içindeki master şifresini güncelle:

```bash
MASTER=$(openssl rand -base64 32)
sed -i "s/^admin_passwd.*/admin_passwd = $MASTER/" /opt/odoo/odoo.conf
echo "Master password: $MASTER"   # → parola yöneticine kaydet; sonra bu echo'u history'den temizle
```

> 📌 `.env` ve `odoo.conf` git'e girmez — şifreler yalnızca sunucuda yaşar.

## 3. Veri Taşıma (local dev → prod)

### a) Local'de dök al

```bash
cd ~/odoo-project
docker compose exec -T db pg_dump -U odoo -d odoo19_dev --no-owner > /tmp/odoo19_dev.sql

# Filestore (ekler/fotoğraflar) ayrıca şart:
docker compose exec web tar cz -C /var/lib/odoo .local/share/Odoo/filestore/odoo19_dev > /tmp/filestore.tgz
```

### b) Sunucuya gönder

```bash
scp /tmp/odoo19_dev.sql /tmp/filestore.tgz user@<sunucu-ip>:/opt/odoo/
```

### c) Sunucuda restore

```bash
cd /opt/odoo
docker compose up -d db        # önce sadece DB

createdb_prod=$(docker compose exec -T db createdb -U odoo odoo_prod 2>&1)
docker compose exec -T db psql -U odoo -d odoo_prod < /opt/odoo/odoo19_dev.sql

# Filestore geri yükle (konteyner içine)
docker compose up -d web && sleep 10
W=$(docker compose ps -q web)
docker exec -i $W mkdir -p /var/lib/odoo/.local/share/Odoo/filestore/odoo_prod
docker exec -i $W \
  tar xz -C /var/lib/odoo/.local/share/Odoo/filestore/odoo_prod --strip=0 \
  < /opt/odoo/filestore.tgz
```

> `filestore.tgz` içindeki yol `.local/share/...` ile başlıyor olmalı (a'daki tar komutu bu şekilde üretir). Restore sonrası `docker compose restart web` ve dosya sahipliği: `docker exec $W chown -R odoo: /var/lib/odoo/.local/share/Odoo/filestore/odoo_prod`.

### d) Modülleri doğrula / yükselt

```bash
docker compose exec web odoo -c /etc/odoo/odoo.conf -d odoo_prod \
  -u my_first_module,sale_custom,buksu_hakedis,nisa_pos_sync,buksu_stok_saha,telegram_notify,mini_helpdesk \
  --stop-after-init
docker compose restart web
```

`dbfilter = ^odoo_prod$` + `list_db = False` sayesinde URL tek DB'ye bağlanır ve DB listeleme kapatılır.

## 4. Caddy ile HTTPS

```bash
docker compose up -d
docker compose ps              # üç servis running/healthy olmalı
docker compose logs caddy      # "certificate obtained successfully" bekle
```

Sertifika otomatik gelir; `odoo.conf`'daki `proxy_mode = True` şart (reverse proxy arkasında zorunlu). Sonra:

```
https://odoo.yasinkaracam.com
```

## 5. Canlıda Yapılması Gerekenler

- **Admin şifresi:** dev DB'den gelecek şifreyi güçlendir veya değiştir
- **Sistem parametreleri:** `telegram_notify.bot_token` / `chat_id`, `nisa_pos_sync.webhook_key` (canlıda mutlaka güçlü değer ver, POS tarafına da aynısını gir), `nisa_pos_sync.api_url` (mock'u KAPAT: `mock_enabled` → boş/devre dışı)
- **Developer mode** demo görüntüsü için kapalı olsun
- Mail (SMTP) gerekiyorsa Ayarlar → Teknik → SMTP; aksi halde Telegram bildirimleri yeterli

## 6. Günlük İşletim

| İşlem | Komut |
|---|---|
| Servis durumu | `docker compose ps` |
| Odoo logu | `docker compose logs web --tail 100 -f` |
| Yeni modül | `docker compose exec web odoo -c /etc/odoo/odoo.conf -d odoo_prod -i <modul> --stop-after-init && docker compose restart web` |
| Günlük DB yedeği | `docker compose exec -T db pg_dump -U odoo -d odoo_prod > /opt/odoo/backups/daily-$(date +%F).sql` (cron: `0 3 * * *`) |
| Filestore yedeği | `docker exec $(docker compose ps -q web) tar cz -C /var/lib/odoo .local/share/Odoo/filestore/odoo_prod > /opt/odoo/backups/fs-$(date +%F).tgz` |
| Versiyon güncelleme | `docker compose pull && docker compose up -d && docker compose exec web odoo -c /etc/odoo/odoo.conf -d odoo_prod -u all --stop-after-init` |

## 7. Sık Karşılaşılan Sorunlar

| Belirti | Neden | Çözüm |
|---|---|---|
| Caddy sertifika alamıyor | DNS yayılmamış / 80 port kapalı | `dig +short odoo...`, `ufw allow 80` |
| `psycopg2.OperationalError` | DB şifre uyumsuzluğu | `.env` değerlerini doğrula, `docker compose down && up -d` |
| `column ... does not exist` | Model alanı DB'ye yansımadı | ilgili modülü `-u` ile yükselt |
| SafeMode / Age dışı hatalar HTTPS'te | `proxy_mode` eksik | `odoo.conf` kontrol + `docker compose restart web` |
| Mail göndermiyor | SMTP yapılmamış | SMTP kur veya Telegram bildirimleriyle telafi et |
| Cron bildirimleri beklenir | key/param eksik | System Parameters kontrol + cron "Run Manually" testi |

---

Özet: `odoo/odoo` şifresi canlıda asla kullanılmaz; DB'ye host erişimi yoktur; master şifre ve DB şifresi rastgele üretilip sunucu dışında saklanmaz; `.env` versiyonlanmaz; yedekler cron ile düzenli, restore adımı doğrulanmış.
