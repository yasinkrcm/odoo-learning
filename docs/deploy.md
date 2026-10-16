# 🚀 Canlıya Alma Rehberi (VPS + Docker)

Hedef: özel bir domain (`odoo.example.com`) üzerinde, geliştirme verisiyle çalışan kalıcı bir Odoo 19 kurulumu.

```
Tarayıcı → Reverse proxy (Caddy veya nginx) → odoo (127.0.0.1:8069) → postgres (host'a açık değil)
```

> Sunucuda **zaten nginx + başka siteler varsa** Kurulum B (nginx) yolunu izle;
> Caddy'yi 80/443'te başlatma — mevcut siteleri bozar.

---

## 0. Ön Koşullar

- VPS: Ubuntu, en az **2 GB RAM + 20 GB disk**
- DNS: `<odoo-domain>` için **A record → sunucu IP**; doğrula: `dig +short <odoo-domain>`
- 80/443 erişilebilir (sadece Kurulum A: Caddy)

---

## 1. Dosyalar ve Sunucu Hazırlığı

```bash
# local (Mac) tarafında:
git clone https://github.com/yasinkrcm/odoo-learning.git /tmp/odoo-learning

# sunucuya taşı (home dizini de olur, /opt kök izni gerekir):
rsync -av --delete /tmp/odoo-learning/addons/ user@<sunucu-ip>:~/odoo-live/addons/
rsync -av /tmp/odoo-learning/deploy/ user@<sunucu-ip>:~/odoo-live/
```

`docker-compose.yml` (deploy/ içindeki) varsayılan **boş-VPS (Kurulum A)** profillidir:
DB host'a kapalı, healthcheck'li, volumes izole adlı. Kurulum B için aşağıdaki değişiklikleri uygula.

---

## 2. Secrets — bizzat sunucuda üret

```bash
cd ~/odoo-live
openssl rand -hex 24        # çıktı → .env POSTGRES_PASSWORD
openssl rand -base64 32     # çıktı → odoo.conf admin_passwd
cp deploy/.env.example .env   # sonra nano ile doldur
nano .env
sed -i "s/^admin_passwd.*/admin_passwd = <GENERATED>/" odoo.conf
chmod 600 .env    # ⚠️ .env 600, odoo.conf ise MUTLAKA 644 kalmalı!
```

**Kritik tuzak:** `odoo.conf`'ta `db_password` satırı **yoktur/onaylanmaz**.
wait-for-psql.py conf'taki değere öncelik verir; `db_password = odoo` bırakıp
.env'de güçlü şifre üretirsen konteyner sonsuz "password authentication failed"
döngüsüne girer. Conf'ta db_* boş bırak, .env (HOST/USER/PASSWORD) yönetsin.

---

## 3. Kurulum A — Boş VPS (Caddy otomatik HTTPS)

```bash
docker compose version
docker compose up -d db
docker compose up -d web
docker compose logs caddy      # sertifika "obtained successfully"
curl -I https://<odoo-domain>  # 200 beklenir
```

---

## 4. Kurulum B — nginx zaten var (80/443 dolu)

1. **Compose'da caddy servisini kaldır**, web `ports` bilgisine ekle:

```yaml
    ports:
      - "127.0.0.1:8069:8069"
```

2. nginx vhost ekle (sudo gerekir) `/etc/nginx/sites-available/odoo.example.com`:

```nginx
server {
    listen 80;
    server_name odoo.example.com;
    location /static/ { proxy_pass http://127.0.0.1:8069; }
    location / {
        proxy_pass http://127.0.0.1:8069;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto https;
        client_max_body_size 100m;
    }
}
```

3. `sudo nginx -t && sudo systemctl reload nginx`
4. Sertifika: `sudo certbot --nginx -d odoo.example.com`
5. Odoo.conf'ta `proxy_mode = True` (deploy/odoo.conf zaten içeriyor).

> Mevcut vhost'ların hiçbirine dokunma; yalnızca yeni dosya ekle.

---

## 5. Veri Taşıma (local dev → prod)

### a) Local'de dök al (gerçek yollarla!)

Docker odoo image'ında filestore `**/var/lib/odoo/filestore/<DB ADI>/**` altında — `.local/share` DEĞİL.

```bash
cd ~/odoo-project
# Hangi DB'de gerçek veri var kontrol et (bu proje: yasin-db):
docker compose exec -T db psql -U odoo -l | grep -vE "postgres|template|^\s*$"
docker compose exec -T db psql -U odoo -d yasin-db -tAc \
  "SELECT (SELECT count(*) FROM res_partner), (SELECT count(*) FROM product_template), (SELECT count(*) FROM sale_order)"

docker compose exec -T db pg_dump -U odoo -d yasin-db --no-owner > /tmp/yasin-db.sql
docker compose exec -T web tar czf - -C /var/lib/odoo filestore/yasin-db > /tmp/filestore.tgz
```

### b) Sunucuya gönder

```bash
rsync -av /tmp/yasin-db.sql /tmp/filestore.tgz user@<sunucu-ip>:~/odoo-live/
```

### c) Sunucuda restore

```bash
cd ~/odoo-live
docker compose up -d db
# healthcheck bekle:
for i in $(seq 1 20); do docker inspect -f '{{.State.Health.Status}}' odoo-live-db | grep -q healthy && break; sleep 2; done

docker compose exec -T db createdb -U odoo odoo_prod
docker compose exec -T db psql -U odoo -q -d odoo_prod < yasin-db.sql

docker compose up -d web
# Filestore: adını odoo_prod'a çevirip aç (GNU tar --transform)
docker exec -i <web-container> tar xzf - -C /var/lib/odoo \
  --transform "s|^filestore/yasin-db|filestore/odoo_prod|" < filestore.tgz
docker exec <web-container> chown -R odoo:odoo /var/lib/odoo/filestore/odoo_prod
```

### d) Modülleri yükselt

> ⚠️ `docker compose exec web` **değil** — çalışan web 8069'u tuttuğu için
> `exec` içindeki odoo crash olur ("Address already in use"). `run --rm` kullan:

```bash
docker compose run --rm web odoo -c /etc/odoo/odoo.conf -d odoo_prod \
  -u my_first_module,sale_custom,buksu_hakedis,nisa_pos_sync,buksu_stok_saha,telegram_notify,mini_helpdesk \
  --stop-after-init
docker compose restart web
```

`dbfilter = ^odoo_prod$` + `list_db = False` sayesinde URL tek DB'ye bağlanır.

---

## 6. Canlıda Yapılması Gerekenler

- **Admin şifresi:** dev DB'den gelen şifreyi güçlendir
- **System Parameters:** `telegram_notify.bot_token/chat_id`, `nisa_pos_sync.webhook_key` (güçlü değer), `nisa_pos_sync.api_url`, `mock_enabled` **KAPAT**
- Developer mode demoda kapalı olsun
- Mail SMTP gerekiyorsa Ayarlar → Teknik → SMTP

## 7. Günlük İşletim

| İşlem | Komut |
|---|---|
| Servis durumu | `docker compose ps` |
| Odoo logu | `docker compose logs web --tail 100 -f` |
| Modül yükleme | `docker compose run --rm web odoo -c /etc/odoo/odoo.conf -d odoo_prod -i <modul> --stop-after-init` |
| Günlük DB yedeği | `docker compose exec -T db pg_dump -U odoo -d odoo_prod > backups/daily-$(date +%F).sql` (cron) |
| Filestore yedeği | `docker exec <web-container> tar cz -C /var/lib/odoo filestore/odoo_prod > backups/fs-$(date +%F).tgz` |

## 8. Yeni Modül Yazıp Canlıya Eklemek (standart akış)

```bash
# 1) LOCAL: yaz, test et
cd ~/odoo-project
# addons/my_new_module/ ...  (manifest + models + views + security)
docker compose exec web odoo -d yasin-db -i my_new_module --stop-after-init
docker compose restart web
git add addons/my_new_module && git commit -m "feat: add my_new_module" && git push origin main

# 2) SUNUCU: kodu taşı + yükle
rsync -av --delete ~/odoo-project/addons/ yasin@<sunucu-ip>:~/odoo-live/addons/
ssh yasin@<sunucu-ip>
cd ~/odoo-live
docker compose run --rm web odoo -c /etc/odoo/odoo.conf -d odoo_prod -i my_new_module --stop-after-init
docker compose restart web
```

Kural notları:
- **İlk kurulum `-i`** — sonraki kod/XML değişimleri `-u` ile upgrade ister
- Sunucuda upgrade **mutlaka `docker compose run --rm web`** (exec içindeki odoo
  çalışan 8069'a çarpar: "Address already in use")
- `__manifest__.py` `data` sırası: security.xml (gruplar) → ir.model.access.csv → views
- Odoo 19 tuzakları: `<list>` kullan (`<tree>` ParseError), `stock.move.name`
  kalktı, `user_ids`/`category_id` kaldırıldı — şüphede container'daki çekirdek
  kaynakları doğrula: `docker compose exec web grep -rn "..." /usr/lib/python3/dist-packages/odoo/addons/<app>/`
- Yeni kalıcı model + transient + cron olan her bileşen ACL gerektirir;
  ACL satırındaki `group_id` external id'si security.xml'de önce tanımlanmalı

## 9. Sık Karşılaşılan Sorunlar (bugün gerçekten yaşananlar)

| Belirti | Neden | Çözüm |
|---|---|---|
| web "password authentication failed" döngüsü | `odoo.conf`'taki placeholder `db_password` env'i ezdi | conf'ta db_password satırını SİL, .env yönetsin |
| `grep: /etc/odoo/odoo.conf: Permission denied` | conf 600 (chmod) | `chmod 644 odoo.conf` (gizli şey içermiyor) |
| Upgrade "Address already in use" | `exec` ile upgrade denendi | `docker compose run --rm web odoo ...` |
| restore sonrası boş filestore | tar kesintiye uğradı | `docker exec -i` ile tgz'yi tamamen yeniden aç; `du -sh` ile boyut doğrula |
| Caddy/nginx sertifika alamıyor | DNS henüz yeni IP'yi göstermiyor | `dig +short <domain>` bekle/propagate |
| `psycopg2.OperationalError` | DB şifre uyumsuz | `.env` değerleri + conf'tan db_* silinmiş mi bak |
| `column ... does not exist` | model alanı DB'ye işlenmemiş | ilgili modülü `-u` ile yükselt |
| HTTPS'te anormal davranış | `proxy_mode` eksik | `odoo.conf` kontrol + `docker compose restart web` |
