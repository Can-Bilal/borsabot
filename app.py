import numpy as np
import pandas as pd
import requests
from scipy import stats
import ssl
from urllib.request import urlopen
import telebot
import matplotlib.pyplot as plt
import seaborn as sns
import os
import logging
import yfinance as yf
from dotenv import load_dotenv 


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


load_dotenv()


API_TOKEN = os.getenv("TELEGRAM_API_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY")


if not API_TOKEN:
    logging.error("API Token bulunamadı. Lütfen TELEGRAM_API_TOKEN değişkenini .env dosyasına ekleyin.")
else:
    logging.info("API Token başarıyla yüklendi.")

if not CHAT_ID:
    logging.error("Chat ID bulunamadı. Lütfen TELEGRAM_CHAT_ID değişkenini .env dosyasına ekleyin.")
else:
    logging.info("Chat ID başarıyla yüklendi.")

if not ALPHA_VANTAGE_API_KEY:
    logging.error("Alpha Vantage API Key bulunamadı. Lütfen ALPHA_VANTAGE_API_KEY değişkenini .env dosyasına ekleyin.")
    raise SystemExit("Alpha Vantage API Key bulunamadı. Program sonlandırılıyor.")
else:
    logging.info("Alpha Vantage API Key başarıyla yüklendi.")

bot = telebot.TeleBot(API_TOKEN)

def Hisse_Temel_Veriler():
    url = f"https://www.alphavantage.co/query?function=LISTING_STATUS&apikey={ALPHA_VANTAGE_API_KEY}"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        if not data:
            logging.error("Hisse temel verileri boş döndü.")
            return []
        Hisseler = [item['symbol'] for item in data]
        logging.info("Hisse temel verileri başarıyla alındı.")
        return Hisseler
    except requests.exceptions.RequestException as e:
        logging.error(f"Hisse temel verileri alınırken hata oluştu: {e}")
        return []
    except ValueError as e:
        logging.error(f"Hisse temel verileri işlenirken hata oluştu: {e}")
        return []

def Stock_Prices(Hisse, timeframe='1H'):
    try:
        stock = yf.Ticker(Hisse)
        data = stock.history(period="5d", interval="1h")
        logging.info(f"{Hisse} için fiyat verileri başarıyla alındı.")
        return data
    except Exception as e:
        logging.error(f"{Hisse} için bağlantı hatası: {e}")
        return pd.DataFrame()

def Stock_Prices_Yahoo(Hisse):
    try:
        stock = yf.Ticker(Hisse)
        data = stock.history(period="5d", interval="1h")
        logging.info(f"{Hisse} için alınan veri:\n{data.head()}")
        return data
    except Exception as e:
        logging.error(f"{Hisse} için Yahoo Finance verisi alınırken hata: {e}")
        return pd.DataFrame()

data = Stock_Prices_Yahoo("EREGL.IS")


def Trend_Channel(df):
    best_period = None
    best_r_value = 0
    periods = range(100, 201, 10)
    for period in periods:
        close_data = df['Close'].tail(period)
        x = np.arange(len(close_data))
        slope, intercept, r_value, _, _ = stats.linregress(x, close_data)
        if abs(r_value) > abs(best_r_value):
            best_r_value = abs(r_value)
            best_period = period
    return best_period, best_r_value

def List_Trend_Breaks(Hisse, data, best_period, rval=0.85):
    close_data = data['Close'].tail(best_period)
    x_best_period = np.arange(len(close_data))

   
    slope_best_period, intercept_best_period, r_value_best_period, _, _ = stats.linregress(x_best_period, close_data)
    trendline = slope_best_period * x_best_period + intercept_best_period
    upper_channel = trendline + (trendline.std() * 1.1)
    lower_channel = trendline - (trendline.std() * 1.1)

    upper_diff = upper_channel - close_data
    lower_diff = close_data - lower_channel
    last_upper_diff = upper_diff.iloc[-1]
    last_lower_diff = lower_diff.iloc[-1]

    trend_strength = "GÜÇLÜ TREND" if abs(r_value_best_period) > 0.5 else "ZAYIF TREND"
    break_price = close_data.iloc[-1]

    if abs(r_value_best_period) > rval:
        if last_upper_diff < 0:
            return (f'{Hisse}: 📈 Yukarı Yönlü Kırılımlar\n'
                    f'Trend Gücü: {abs(r_value_best_period):.2f} - {trend_strength}\n'
                    f'Kırılım Fiyatı: {break_price:.2f}', True, 'up')
        elif last_lower_diff < 0:
            return (f'{Hisse}: 📉 Aşağı Yönlü Kırılımlar\n'
                    f'Trend Gücü: {abs(r_value_best_period):.2f} - {trend_strength}\n'
                    f'Kırılım Fiyatı: {break_price:.2f}', True, 'down')
    return None, False, None

def plot_trend_channel(Hisse, data, best_period, trend_break=None):
    logging.info(f"Grafik oluşturuluyor: {Hisse}")
    plt.figure(figsize=(14, 7))
    sns.lineplot(x=data.index, y='Close', data=data, label='Kapanış Fiyatı')

    close_data = data['Close'].tail(best_period)
    x = np.arange(len(close_data))
    slope, intercept, r_value, _, _ = stats.linregress(x, close_data)
    trendline = slope * x + intercept
    plt.plot(close_data.index, trendline, color='orange', label='Trend Çizgisi')

    upper_channel = trendline + (trendline.std() * 1.1)
    lower_channel = trendline - (trendline.std() * 1.1)
    plt.plot(close_data.index, upper_channel, color='green', linestyle='--', label='Üst Kanal')
    plt.plot(close_data.index, lower_channel, color='red', linestyle='--', label='Alt Kanal')

    if trend_break:
        if trend_break[2] == 'up':
            plt.scatter(data.index[-1], data['Close'].iloc[-1], color='green', marker='^', s=100, label='Yukarı Kırılım')
        elif trend_break[2] == 'down':
            plt.scatter(data.index[-1], data['Close'].iloc[-1], color='red', marker='v', s=100, label='Aşağı Kırılım')

    plt.title(f'{Hisse} Fiyat ve Trend Analizi')
    plt.xlabel('Zaman')
    plt.ylabel('Fiyat')
    plt.legend()
    plt.grid(True)

    if not os.path.exists('plots'):
        os.makedirs('plots')
        logging.info("'plots' klasörü oluşturuldu.")
    plot_path = f'plots/{Hisse}_trend.png'
    plt.savefig(plot_path)
    plt.close()
    logging.info(f"Grafik kaydedildi: {plot_path}")
    return plot_path

def analyze_and_notify():
    Hisseler = Hisse_Temel_Veriler()
    up_breaks = []
    down_breaks = []
    plots_to_send = []
    trend_data = []  # Tabloyu tutmak için liste

    for hisse in Hisseler:
        try:
            data = Stock_Prices(hisse)
            if data.empty:
                logging.warning(f'{hisse} için veri bulunamadı.')
                continue
            best_period, best_r_value = Trend_Channel(data)
            if best_period is None:
                logging.warning(f'{hisse} için uygun trend periyodu bulunamadı.')
                continue
            result, status, direction = List_Trend_Breaks(hisse, data, best_period)
            if result:
                trend_data.append({
                    'Hisse': hisse,
                    'Kırılım Durumu': result.split('\n')[0],
                    'Trend Gücü': result.split('\n')[1],
                    'Kırılım Fiyatı': result.split('\n')[2].split(': ')[1],
                    'Yön': direction
                })

                plot_path = plot_trend_channel(hisse, data, best_period, trend_break=(result, status, direction))
                plots_to_send.append(plot_path)

            logging.info(f'{hisse} kontrol ediliyor: {status}')
        except Exception as e:
            logging.error(f'Hisse {hisse} için hata: {e}')
            continue

  
    trend_df = pd.DataFrame(trend_data)
    trend_df.to_csv('trend_kirilimlar.csv', index=False)
    logging.info(f"Tablo kaydedildi: trend_kirilimlar.csv")

    
    if up_breaks:
        up_message = "📈 Yukarı Yönlü Kırılımlar:\n" + "\n".join(up_breaks) + "\n\n"
        logging.info(up_message)
        bot.send_message(CHAT_ID, up_message, parse_mode='Markdown')
    else:
        no_up_message = "📈 Yukarı yönlü kırılım tespit edilmedi.\n\n"
        logging.info(no_up_message)
        bot.send_message(CHAT_ID, no_up_message, parse_mode='Markdown')

    if down_breaks:
        down_message = "📉 Aşağı Yönlü Kırılımlar:\n" + "\n".join(down_breaks)
        logging.info(down_message)
        bot.send_message(CHAT_ID, down_message, parse_mode='Markdown')
    else:
        no_down_message = "📉 Aşağı yönlü kırılım tespit edilmedi."
        logging.info(no_down_message)
        bot.send_message(CHAT_ID, no_down_message)

    for plot in plots_to_send:
        try:
            with open(plot, 'rb') as photo:
                bot.send_photo(CHAT_ID, photo)
                logging.info(f"Grafik Telegram'a gönderildi: {plot}")
        except Exception as e:
            logging.error(f"Grafik gönderilirken hata oluştu ({plot}): {e}")

def main():
    analyze_and_notify()
    bot.infinity_polling()  

if __name__ == "__main__":
    main()