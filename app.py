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


sender = "etf@api.nazarko-company.pl"
receivers = ["rafal.nazarko@gmail.com"]

app = flask.Flask(__name__)
app.config["DEBUG"] = True


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

            server = smtplib.SMTP_SSL('mail.nazarko-company.pl', 465)
            server.login(sender, "u]5RpnRX?a))")

            current_balance = 0
            money_invested = 0.0

            # ETFs
            cursor.execute("""CALL `AKTYWA_pobierzWszystkieETFy`();""")
            db_result = cursor.fetchall()
            ETF_current_balance = 0
            ETF_money_invested = 0.0

            etf_info = ""
            for ETF in db_result:
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

                etf_info += f"""
                    <h3><a href="{ETF["strona_do_sledzenia"]}" target="_blank">{ETF["name"]}</a>     {('(x'+str(ETF["ilosc_aktywa"])+')') if "ilosc_aktywa" in ETF else ''} = {format(ETF["currnet_price"]*ex_rate*ETF["ilosc_aktywa"], '.2f')} PLN
                    <span style="color:{'red' if current_price<buy_price else 'green'}; font-size: 15px">({'-' if current_price<buy_price else '+'} { format(100-(current_price/buy_price)*100,'.2f') if current_price<buy_price else format((current_price/buy_price)*100-100,'.2f') if (buy_price > 0 and current_price > 0) else 0}%)</span><em style="font-size: 15px"> from {buy_price} PLN</em></h3>
                    <p style="font-size: 10px; transform: translateY(-16px);"><label> TICKER-ISIN: {ETF["isin"]}</label></p>
                    <p>Description: {ETF["description"]}</p>
                    <div><label style="font-size: 15px; color: green; font-weight: bold;">{ETF["min_value"]} {ETF["currency"]}</label> <img src={ETF["img_source"]} /> <label style="font-size: 15px; color: red; font-weight: bold;">{ETF["max_value"]} {ETF["currency"]}</label></div>
                    <div>&nbsp;</div>
                    <div>Actual price is <span style="font-weight: bold;">{ETF["currnet_price"]} {ETF["currency"]} = {format(ETF["currnet_price"]*ex_rate, '.2f')} PLN</span> which is <span style="font-size: 15px; color: {"red" if ETF["price_indicator"] == 'EXPENSIVE' else "green" if ETF["price_indicator"] == 'CHEAP' else 'black' }; font-weight: bold;">{ETF["price_indicator"]}</span> <em style="font-size: 10px;">({ETF["percentage"]}%)</em></div>
                    <div>&nbsp;</div><hr/><div>&nbsp;</div>
                """
            # BALANCE SUMARY

            current_balance = ETF_current_balance
            money_invested = ETF_money_invested
            current_balance_info = f"""
            <h2 style="font-weight: normal">
            My current summary balance is:
            </h2>
            <table>
                <tr>
                    <th style="text-align: left;">Finance type</th>
                    <th style="text-align: left;padding: 0 50px;">Pricing</th>
                </tr>
                <tr>
                    <td>ETFs</td>
                    <td style="padding: 0 50px">
                            {format(ETF_current_balance, '.2f')} PLN <span style="color:{'red' if ETF_current_balance<ETF_money_invested else 'green'}; font-size: 15px">({'-' if ETF_current_balance<ETF_money_invested else '+'} { format(100-(ETF_current_balance/ETF_money_invested)*100,'.2f') if ETF_current_balance<ETF_money_invested else format((ETF_current_balance/ETF_money_invested)*100-100,'.2f') if (ETF_money_invested > 0 and ETF_current_balance > 0) else 0}%)</span><em style="font-size: 10px"> from {ETF_money_invested} PLN</em>
                    </td>
                </tr>
                <tr>
                    <td style="font-weight: bold; font-size: 30px;line-height: 30px;">SUMMARY:</td>
                    <td style="padding: 0 50px;font-weight: bold; font-size: 30px;line-height: 30px;">
                        {format(current_balance, '.2f')} PLN <span style="color:{'red' if current_balance<money_invested else 'green'}; font-size: 20px;line-height: 20px;">({'-' if current_balance<money_invested else '+'} { format(100-(current_balance/money_invested)*100,'.2f') if current_balance<money_invested else format((current_balance/money_invested)*100-100,'.2f') if (money_invested > 0 and current_balance > 0) else 0}%)</span><em style="font-size: 20px;line-height: 20px;"> from {money_invested} PLN</em>
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
            </body>
            </html>"""

            message_body = MIMEText(html, 'html')
            msg.attach(message_body)
            server.send_message(msg)
            server.quit()
            return current_balance_info + etf_info


if __name__ == '__main__':
    app.run()
