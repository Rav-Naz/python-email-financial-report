import flask
import requests
from bs4 import BeautifulSoup
from flask import jsonify
import smtplib
import json
from email.message import EmailMessage
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import pymysql
import os
from dotenv import load_dotenv
load_dotenv()


sender = os.environ.get('EMAIL_SENDER')
receivers = [os.environ.get('EMAIL_RECIEVER')]

app = flask.Flask(__name__)
app.config["DEBUG"] = True


def info_builder(nazwa, isin, opis, strona_do_sledzenia, ilosc_aktywa, waluta_glowna, akt_cena, akt_cena_pln, zak_cena_pln, ex_rate, wart_min, wart_max, wart_min_max_proc, indicator):
    return f"""
                    <h3><a href="{strona_do_sledzenia}" target="_blank">{nazwa}</a>     {('(x'+str(ilosc_aktywa)+')')} = {format(akt_cena*ex_rate*ilosc_aktywa, '.2f')} PLN
                    <span style="color:{'red' if akt_cena_pln<zak_cena_pln else 'green'}; font-size: 15px">({'-' if akt_cena_pln<zak_cena_pln else '+'} { format(100-(akt_cena_pln/zak_cena_pln)*100,'.2f') if akt_cena_pln<zak_cena_pln else format((akt_cena_pln/zak_cena_pln)*100-100,'.2f') if (zak_cena_pln > 0 and akt_cena_pln > 0) else 0}%)</span><em style="font-size: 15px"> from {zak_cena_pln} PLN</em></h3>
                    <p style="font-size: 10px; transform: translateY(-16px);"><label> TICKER-ISIN: {isin}</label></p>
                    <p>Description: {opis}</p>
                    <div style="display: flex; flex-direction: row; align-items: center">
                    
                    <label style="font-size: 15px; color: green; font-weight: bold;">{format(wart_min, '.2f')} {waluta_glowna}</label>
                    <div style="width: 100px; height: 20px; background-color:lightgrey; display: block; margin: 0 10px;border: 1px solid grey; border-radius: 5px;overflow: hidden;"><div style="width: 3px; height: 20px; background-color:red; margin-left: {wart_min_max_proc-1.5}px;"></div></div>
                    <label style="font-size: 15px; color: red; font-weight: bold;">{format(wart_max, '.2f')} {waluta_glowna}</label>
                    
                    </div>
                    <div>&nbsp;</div>
                    <div>Actual price is <span style="font-weight: bold;">{format(akt_cena, '.2f')} {waluta_glowna} {'='+format(akt_cena*ex_rate, '.2f')+' PLN' if waluta_glowna != 'PLN' else ''}</span> which is <span style="font-size: 15px; color: {"red" if indicator == 'EXPENSIVE' else "green" if indicator == 'CHEAP' else 'black' }; font-weight: bold;">{indicator}</span> <em style="font-size: 10px;">({wart_min_max_proc}%)</em></div>
                    <div>&nbsp;</div><hr/><div>&nbsp;</div>
                """


def table_row_builder(title, current_balance, invested_money):
    return f"""
                <tr>
                    <td>{title}</td>
                    <td style="padding: 0 50px">
                            {format(current_balance, '.2f')} PLN <span style="color:{'red' if current_balance<invested_money else 'green'}; font-size: 15px">({'-' if current_balance<invested_money else '+'} { format(100-(current_balance/invested_money)*100,'.2f') if current_balance<invested_money else format((current_balance/invested_money)*100-100,'.2f') if (invested_money > 0 and current_balance > 0) else 0}%)</span><em style="font-size: 10px"> from {format(invested_money, '.2f')} PLN</em>
                    </td>
                </tr>
    """


@app.route('/', methods=['GET'])
def home():
    return "<h1>My ETFs daily check</h1><p>/etf-api/daily-check</p>"


@app.route('/etf-api/daily-check', methods=['GET'])
def api_all():
    connection = pymysql.connect(host='localhost',
                                 user=os.environ.get('DB_USER'),
                                 password=os.environ.get('DB_USER_PASSWORD'),
                                 database=os.environ.get('DB_NAME'),
                                 cursorclass=pymysql.cursors.DictCursor)

    with connection:
        with connection.cursor() as cursor:

            today_exchanges_rates = json.loads(requests.get(
                'https://api.nbp.pl/api/exchangerates/tables/A?format=json').text)[0]['rates']

            server = smtplib.SMTP_SSL(os.environ.get('SMTP_SERVER'), 465)
            server.login(sender, os.environ.get('SMTP_PASSWORD'))

            current_balance = 0
            money_invested = 0.0

            # ETFs
            cursor.execute("""CALL `AKTYWA_pobierzWszystkieETFy`();""")
            db_etfs = cursor.fetchall()
            ETF_current_balance = 0
            ETF_money_invested = 0.0

            etf_info = f"""
                <h2>ETFs:</h2><br>
            """
            for ETF in db_etfs:
                ETF['ilosc_aktywa'] = int(ETF['ilosc_aktywa'])
                URL = ETF['strona_do_sledzenia']
                page = requests.get(URL)
                soup = BeautifulSoup(page.content, "html.parser")
                prices = soup.find("div", class_="infobox mb-0")
                val = prices.find("div", class_="val").find_all("span")
                for idx, val in enumerate(val):
                    if idx == 0:
                        ETF["currency"] = val.text.strip()
                    elif idx == 1:
                        ETF["currnet_price"] = float(val.text.strip())
                ex_rate = [
                    element for element in today_exchanges_rates if element['code'] == ETF["currency"]][0]['mid']
                current_price = (ETF["currnet_price"] *
                                 ETF["ilosc_aktywa"] * ex_rate)
                buy_price = ETF["wycena_w_pln"]
                ETF_current_balance += current_price
                ETF_money_invested += buy_price
                valchart = prices.find("div", class_="valchart")
                for idx, val in enumerate(valchart):
                    if idx == 0:
                        ETF["min_value"] = float(val.text.strip())
                    elif idx == 1:
                        ETF["img_source"] = 'https://www.justetf.com' + val['src']
                    elif idx == 2:
                        ETF["max_value"] = float(val.text.strip())
                ETF["percentage"] = int(
                    (ETF["currnet_price"]-ETF["min_value"])/(ETF["max_value"]-ETF["min_value"])*100)
                ETF["price_indicator"] = 'EXPENSIVE' if ETF["percentage"] > 60 else 'CHEAP' if ETF["percentage"] < 40 else 'NORMAL'
                ETF["name"] = soup.find(
                    "span", class_="v-ellip").find("span").text.strip()[3:]
                # investement_strategy = val.parent.parent.parent.parent
                ETF["description"] = prices.parent.parent.find_all(
                    "div", class_="col-sm-6")[1].find("p").text.strip()
                try:
                    cursor.execute(
                        f"""CALL MIGAWKI_dodaj('{ETF['isin']}', {ETF['currnet_price']}, '{ETF["currency"]}', {ex_rate});""")
                    connection.commit()
                except:
                    print("err")

                etf_info += info_builder(ETF["name"], ETF["isin"], ETF["description"], ETF["strona_do_sledzenia"], ETF["ilosc_aktywa"], ETF["currency"], ETF["currnet_price"],
                                         current_price, buy_price, ex_rate, ETF["min_value"], ETF["max_value"], ETF["percentage"], ETF["price_indicator"])
            # Shares
            cursor.execute("""CALL `AKTYWA_pobierzWszystkieAkcje`();""")
            db_shares = cursor.fetchall()
            shares_current_balance = 0
            shares_money_invested = 0.0

            shares_info = f"""
                <h2>Shares:</h2><br>
            """
            for SHARE in db_shares:
                SHARE['ilosc_aktywa'] = int(SHARE['ilosc_aktywa'])
                URL = SHARE['strona_do_sledzenia']
                page = requests.get(URL)
                soup = BeautifulSoup(page.content, "html.parser")

                SHARE["currnet_price"] = float(
                    soup.find("span", class_="q_ch_act").text.strip())
                SHARE["description"] = ''
                opis = soup.find("div", class_="profileDesc")
                if opis != None:
                    SHARE["description"] = opis.find("p").find(
                        "span", class_="hidden").text.strip()
                tab = soup.find(
                    "table", class_="profileSummary").find_all('tr')
                SHARE["min_value"] = 1.0
                SHARE["max_value"] = 1.0
                for tr in tab:
                    th = tr.find('th')
                    if th != None and th.text == 'Min 52 tyg:':
                        SHARE["min_value"] = float(tr.find('td').text.strip())
                    elif th != None and th.text == 'Max 52 tyg:':
                        SHARE["max_value"] = float(tr.find('td').text.strip())
                ex_rate = [
                    element for element in today_exchanges_rates if element['code'] == SHARE["nazwa_waluty"]][0]['mid'] if SHARE["nazwa_waluty"] != 'PLN' else 1
                current_price = (SHARE["currnet_price"] *
                                 SHARE["ilosc_aktywa"] * ex_rate)
                buy_price = SHARE["wycena_w_pln"]
                shares_current_balance += current_price
                shares_money_invested += buy_price
                valchart = prices.find("div", class_="valchart")

                SHARE["percentage"] = int(
                    (SHARE["currnet_price"]-SHARE["min_value"])/(SHARE["max_value"]-SHARE["min_value"])*100)
                SHARE["price_indicator"] = 'EXPENSIVE' if SHARE["percentage"] > 60 else 'CHEAP' if SHARE["percentage"] < 40 else 'NORMAL'
                try:
                    cursor.execute(
                        f"""CALL MIGAWKI_dodaj('{SHARE['isin']}', {SHARE['currnet_price']}, '{SHARE["nazwa_waluty"]}', {ex_rate});""")
                    connection.commit()
                except:
                    print("err")

                shares_info += info_builder(SHARE["nazwa_aktywa"], SHARE["isin"], SHARE["description"], SHARE["strona_do_sledzenia"], SHARE["ilosc_aktywa"], SHARE["nazwa_waluty"], SHARE["currnet_price"],
                                            current_price, buy_price, ex_rate, SHARE["min_value"], SHARE["max_value"], SHARE["percentage"], SHARE["price_indicator"])
            # BALANCE SUMARY

            current_balance = ETF_current_balance + shares_current_balance
            money_invested = ETF_money_invested + shares_money_invested
            current_balance_info = f"""
            <h2 style="font-weight: normal">
            My current summary balance is:
            </h2>
            <table>
                <tr>
                    <th style="text-align: left;">Finance type</th>
                    <th style="text-align: left;padding: 0 50px;">Pricing</th>
                </tr>
                {table_row_builder('ETFs', ETF_current_balance, ETF_money_invested)}
                {table_row_builder('Shares', shares_current_balance, shares_money_invested)}
                <tr>
                    <td style="font-weight: bold; font-size: 30px;line-height: 30px;">SUMMARY:</td>
                    <td style="padding: 0 50px;font-weight: bold; font-size: 30px;line-height: 30px;">
                        {format(current_balance, '.2f')} PLN <span style="color:{'red' if current_balance<money_invested else 'green'}; font-size: 20px;line-height: 20px;">({'-' if current_balance<money_invested else '+'} { format(100-(current_balance/money_invested)*100,'.2f') if current_balance<money_invested else format((current_balance/money_invested)*100-100,'.2f') if (money_invested > 0 and current_balance > 0) else 0}%)</span><em style="font-size: 20px;line-height: 20px;"> from {format(money_invested, '.2f')} PLN</em>
                    </td>
                </tr>
            </table>
            <div>&nbsp;</div><div>&nbsp;</div>
            """

            # EMAIL SEND

            msg = MIMEMultipart('alternative')
            msg['Subject'] = 'Today\'s financial report'
            msg['From'] = f'My Financial Notifier<{sender}>'
            msg['To'] = receivers[0]
            html = f"""\
            <html>
            <head></head>
            <body>
                {current_balance_info}
                {etf_info}
                {shares_info}
            </body>
            </html>"""

            message_body = MIMEText(html, 'html')
            msg.attach(message_body)
            server.send_message(msg)
            server.quit()
            return current_balance_info + etf_info + shares_info


if __name__ == '__main__':
    app.run()
