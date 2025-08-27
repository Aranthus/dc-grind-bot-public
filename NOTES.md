## Proje Yapısı
- `discord_selfbot.py`: Ana bot kodu
- `config.py`: Bot yapılandırması ve API anahtarları
- `prompt.py`: AI sistem promptu ve davranış kuralları
- `users.json`: Kullanıcı verileri


## Sorunlar
- Token limit sorunu kullanıcıyla 50-60 mesaj yazınca bot api error vericek. çünkü chat basına 2048 token limiti var

## 🚨 KRİTİK SORUN: Bot çok yapay davranıyor!
**Problem:** Bot iki kişi arasındaki direkt konuşmalara karışıyor

## Eklenecekler 
- sohbet başlatma becerisi (eklendi ama geliştirilebilir) bozuk şu anlık.


## Önemli Notlar
- Açılır Pop-up Seklinde dökümentasyon olustur bu sayede önemli bilgileri oraya yazabilelim. 

## Geliştirme
- Promptları insan olana kadar geliştirmek gerekli
- Aynı kelimeyi sürekli tekrar etmeme (Prompt) base prompta ekle
- sohbet başlatma becerisi (eklendi ama geliştirilebilir)

## Proje özelinde
- Promptları her seferinde proje özelinde eğitmemiz gerek
