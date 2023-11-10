from email.mime.image import MIMEImage
import flask
import requests
from bs4 import BeautifulSoup
import smtplib
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import pymysql
import os
import matplotlib.pyplot as plt
import matplotlib.dates as matdate
import uuid
from datetime import datetime, timedelta

from dotenv import load_dotenv
load_dotenv()


sender = os.environ.get('EMAIL_SENDER')
receivers = [os.environ.get('EMAIL_RECIEVER')]

app = flask.Flask(__name__)
app.config["DEBUG"] = True

msg = MIMEMultipart('alternative')


def info_builder(nazwa, isin, opis, strona_do_sledzenia, ilosc_aktywa, waluta_glowna, akt_cena, akt_cena_pln, zak_cena_pln, ex_rate, wart_min, wart_max, wart_min_max_proc, indicator, kurs_zakupu, kurs_zakupu_min_max_proc):
    internalFileName = '%s-%s' % (
        datetime.now().strftime('%Y%m%d%H%M%S'), uuid.uuid4())
    try:
        fp = open(f'images/{nazwa}.png', 'rb')
        msgImage = MIMEImage(fp.read())
        fp.close()
        msgImage.add_header('Content-ID', f'<{internalFileName}>')
        msg.attach(msgImage)
    except:
        print('no image')

    x = ""
    if wart_min != wart_max:
        x = f"""
        <div style="display: flex; flex-direction: row; align-items: start;">

                    <label style="font-size: 15px; color: green; font-weight: bold; line-height: 20px">{format(wart_min, '.2f')} {waluta_glowna}</label>

                    <div style="display: flex; max-width: 100px; flex-direction: column; justify-content: center; align-items: center; margin: 0 10px;">
                        <div style="width: 100px; height: 20px; background: linear-gradient(90deg, rgba(17,250,0,1) 0%, rgba(255,239,0,1) 50%, rgba(255,0,0,1) 100%); display: grid; border: 1px solid black; border-radius: 5px;overflow: hidden;">
                        <div style="width: 2px; height: 20px; background-color:black; margin-left: {wart_min_max_proc-1}px; position: absolute; grid-column: 1; grid-row: 1;"></div>
                            </div>
                    </div>

                    <label style="font-size: 15px; color: red; font-weight: bold;line-height: 20px;">{format(wart_max, '.2f')} {waluta_glowna}</label>

                    </div>

                    <div>&nbsp;</div>
                    <div>Actual price is <span style="font-weight: bold;">{format(akt_cena, '.2f')} {waluta_glowna} {'= '+format(akt_cena*ex_rate, '.2f')+' PLN' if waluta_glowna != 'PLN' else ''}</span> which is <span style="font-size: 15px; color: {"red" if indicator == 'EXPENSIVE' else "green" if indicator == 'CHEAP' else 'black' }; font-weight: bold;">{indicator}</span> <em style="font-size: 10px;">({wart_min_max_proc}%)</em></div>
                    """

    return f"""
                    <h3><a href="{strona_do_sledzenia}" target="_blank">{nazwa}</a>     {('(x'+"%.2f"% round(ilosc_aktywa, 2)+')')} = {format(akt_cena*ex_rate*ilosc_aktywa, '.2f')} PLN
                    <span style="color:{'red' if akt_cena_pln<zak_cena_pln else 'green'}; font-size: 15px">({'-' if akt_cena_pln<zak_cena_pln else '+'} { format(100-(akt_cena_pln/zak_cena_pln)*100,'.2f') if akt_cena_pln<zak_cena_pln else format((akt_cena_pln/zak_cena_pln)*100-100,'.2f') if (zak_cena_pln > 0 and akt_cena_pln > 0) else 0}%)</span><em style="font-size: 15px"> from {zak_cena_pln} PLN</em></h3>
                    <p style="font-size: 10px; transform: translateY(-16px);"><label> TICKER-ISIN: {isin}</label></p>
                    <p>Description: {opis}</p>
                    {x}
                    <img src="cid:{internalFileName}">
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


def clamp(n, smallest, largest):
    return max(smallest, min(n, largest))


def createPlots(data, two_axes=True):
    migawki = json.loads(data['json_list'])
    migawki.sort(key=lambda mig: datetime.strptime(mig['data'], "%Y-%m-%d"))
    y1 = []
    y2 = []
    x = []
    for mig in migawki:
        x.append(matdate.date2num(datetime.strptime(mig['data'], "%Y-%m-%d")))
        y1.append(mig['wycena'])
        if two_axes:
            y2.append(mig['wycena']*mig['kurs_do_pln']
                      * int(data['ilosc_aktywa']))
    fig, ax = plt.subplots()
    ax.plot(x,
            y1,
            color="red")
    ax.set_xlabel("Date", fontsize=14)
    ax.set_ylabel(f"Price in {migawki[0]['waluta'] if len(migawki) > 0 else 'PLN'} for single financial asset",
                  color="red",
                  fontsize=14)
    ax.xaxis.set_major_locator(matdate.AutoDateLocator(maxticks=7))
    ax.xaxis.set_major_formatter(matdate.DateFormatter('%d.%m'))
    if two_axes:
        ax2 = ax.twinx()
        ax2.plot(x, y2, color="blue")
        ax2.set_ylabel(f"Overall price in PLN for all assets",
                       color="blue", fontsize=14)
    imgName = "images/"+data['nazwa_aktywa']+".png"
    plt.savefig(imgName)


@app.route('/', methods=['GET'])
def home():
    return "<h1>My ETFs daily check</h1><p>/etf-api/daily-check</p>"


@app.route('/etf-api/daily-check', methods=['GET'])
def api_all():
    global msg
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

            msg = MIMEMultipart('alternative')
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
                ETF['ilosc_aktywa'] = float(ETF['ilosc_aktywa'])
                URL = ETF['strona_do_sledzenia']
                page = requests.get(URL)
                soup = BeautifulSoup(page.content, "html.parser")
                ETF["currnet_price"] = float(soup.find("span", class_="mod-ui-data-list__value").text.replace(',',''))
                ETF["currency"] = URL.split(":")[-1].replace("GBX", "GBP")
                ex_rate = [element for element in today_exchanges_rates if element['code'] == ETF["currency"]][0]['mid']
                current_price = (ETF["currnet_price"] *
                                 ETF["ilosc_aktywa"] * ex_rate)
                buy_price = ETF["wycena_w_pln"]
                ETF_current_balance += current_price
                ETF_money_invested += buy_price
                ETF["percentage"] = int(
                    (ETF["currnet_price"]-ETF["min_value"])/(ETF["max_value"]-ETF["min_value"])*100)
                ETF["percentage_zakup"] = clamp(int(
                    (ETF["sredni_kurs"]-ETF["min_value"])/(ETF["max_value"]-ETF["min_value"])*100), 0, 100)

                ETF["price_indicator"] = 'EXPENSIVE' if ETF["percentage"] > 60 else 'CHEAP' if ETF["percentage"] < 40 else 'NORMAL'
                ETF["name"] = soup.find(
                    "h1", class_="mod-tearsheet-overview__header__name mod-tearsheet-overview__header__name--large").text.strip()
                ETF["description"] = soup.find_all("div", class_="mod-module__content")[3].find("p").text
                try:
                    cursor.execute(
                        f"""CALL MIGAWKI_dodaj('{ETF['isin']}', {ETF['currnet_price']}, '{ETF["currency"]}', {ex_rate});""")
                    connection.commit()
                    migawki = json.loads(ETF['json_list'])
                    migawki.append({'data': datetime.now().strftime(
                        "%Y-%m-%d"), 'wycena': ETF['currnet_price'], 'waluta': ETF["currency"], 'kurs_do_pln': ex_rate})
                except:
                    pass

                createPlots(ETF)

                etf_info += info_builder(ETF["name"], ETF["isin"], ETF["description"], ETF["strona_do_sledzenia"], ETF["ilosc_aktywa"], ETF["currency"], ETF["currnet_price"],
                                         current_price, buy_price, ex_rate, ETF["min_value"], ETF["max_value"], ETF["percentage"], ETF["price_indicator"], ETF["sredni_kurs"], ETF["percentage_zakup"])
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
                        SHARE["min_value"] = float(
                            tr.find('td').text.strip())
                    elif th != None and th.text == 'Max 52 tyg:':
                        SHARE["max_value"] = float(
                            tr.find('td').text.strip())
                ex_rate = [
                    element for element in today_exchanges_rates if element['code'] == SHARE["nazwa_waluty"]][0]['mid'] if SHARE["nazwa_waluty"] != 'PLN' else 1
                current_price = (SHARE["currnet_price"] *
                                 SHARE["ilosc_aktywa"] * ex_rate)
                buy_price = SHARE["wycena_w_pln"]
                shares_current_balance += current_price
                shares_money_invested += buy_price
                # valchart = prices.find("div", class_="valchart")

                SHARE["percentage"] = int(
                    (SHARE["currnet_price"]-SHARE["min_value"])/(SHARE["max_value"]-SHARE["min_value"])*100)
                SHARE["percentage_zakup"] = clamp(int(
                    (ETF["sredni_kurs"]-ETF["min_value"])/(ETF["max_value"]-ETF["min_value"])*100), 0, 100)
                SHARE["price_indicator"] = 'EXPENSIVE' if SHARE["percentage"] > 60 else 'CHEAP' if SHARE["percentage"] < 40 else 'NORMAL'
                try:
                    cursor.execute(
                        f"""CALL MIGAWKI_dodaj('{SHARE['isin']}', {SHARE['currnet_price']}, '{SHARE["nazwa_waluty"]}', {ex_rate});""")
                    connection.commit()
                    migawki = json.loads(SHARE['json_list'])
                    migawki.append({'data': datetime.now().strftime(
                        "%Y-%m-%d"), 'wycena': SHARE['currnet_price'], 'waluta': SHARE["currency"], 'kurs_do_pln': ex_rate})
                except:
                    pass

                createPlots(SHARE)

                shares_info += info_builder(SHARE["nazwa_aktywa"], SHARE["isin"], SHARE["description"], SHARE["strona_do_sledzenia"], SHARE["ilosc_aktywa"], SHARE["nazwa_waluty"], SHARE["currnet_price"],
                                            current_price, buy_price, ex_rate, SHARE["min_value"], SHARE["max_value"], SHARE["percentage"], SHARE["price_indicator"], SHARE["sredni_kurs"], SHARE["percentage_zakup"])

            # Gold
            cursor.execute("""CALL `AKTYWA_pobierzWszystkieZłota`();""")
            db_golds = cursor.fetchall()
            GOLD_current_balance = 0
            GOLD_money_invested = 0.0

            golds_info = f"""
                <h2>Golds:</h2><br>
            """
            for GOLD in db_golds:
                GOLD['ilosc_aktywa'] = int(GOLD['ilosc_aktywa'])
                URL = GOLD['strona_do_sledzenia']
                last_half_year_gold_prices = json.loads(requests.get(
                    'https://api.nbp.pl/api/cenyzlota/last/180/?format=json').text)
                min_value = float('inf')
                max_value = 0
                for value in last_half_year_gold_prices:
                    cena = value['cena']
                    if min_value > cena:
                        min_value = cena
                    elif max_value < cena:
                        max_value = cena
                GOLD["min_value"] = min_value * 31.1
                GOLD["max_value"] = max_value * 31.1
                GOLD["currnet_price"] = last_half_year_gold_prices[len(
                    last_half_year_gold_prices)-1:][0]['cena']*31.1

                ex_rate = [
                    element for element in today_exchanges_rates if element['code'] == ETF["currency"]][0]['mid']
                current_price = (GOLD["currnet_price"] *
                                 GOLD["ilosc_aktywa"] * ex_rate)
                buy_price = GOLD["wycena_w_pln"]
                GOLD['currency'] = 'PLN'
                GOLD_current_balance += current_price
                GOLD_money_invested += buy_price
                GOLD["percentage"] = int(
                    (GOLD["currnet_price"]-GOLD["min_value"])/(GOLD["max_value"]-GOLD["min_value"])*100)
                GOLD["percentage_zakup"] = clamp(int(
                    (GOLD["sredni_kurs"]-GOLD["min_value"])/(GOLD["max_value"]-GOLD["min_value"])*100), 0, 100)

                GOLD["price_indicator"] = 'EXPENSIVE' if GOLD["percentage"] > 60 else 'CHEAP' if GOLD["percentage"] < 40 else 'NORMAL'
                GOLD["description"] = ''
                try:
                    cursor.execute(
                        f"""CALL MIGAWKI_dodaj('{GOLD['isin']}', {GOLD['currnet_price']}, '{GOLD["currency"]}', {ex_rate});""")
                    connection.commit()
                    migawki = json.loads(GOLD['json_list'])
                    migawki.append({'data': datetime.now().strftime(
                        "%Y-%m-%d"), 'wycena': GOLD['currnet_price'], 'waluta': GOLD["currency"], 'kurs_do_pln': ex_rate})
                except:
                    pass

                createPlots(GOLD)

                golds_info += info_builder(GOLD["nazwa_aktywa"], GOLD["isin"], GOLD["description"], GOLD["strona_do_sledzenia"], GOLD["ilosc_aktywa"], GOLD["currency"], GOLD["currnet_price"],
                                           current_price, buy_price, ex_rate, GOLD["min_value"], GOLD["max_value"], GOLD["percentage"], GOLD["price_indicator"], GOLD["sredni_kurs"], GOLD["percentage_zakup"])

            # Bonds
            cursor.execute(
                """CALL `AKTYWA_pobierzWszystkieObligacje`();""")
            db_bonds = cursor.fetchall()
            BOND_current_balance = 0
            BOND_money_invested = 0.0

            bonds_info = f"""
                <h2>Bonds:</h2><br>
            """
            rzymskie = ['I', 'II', 'III', 'IV', 'V', 'VI',
                        'VII', 'VIII', 'IX', 'X', 'XI', 'XII']
            for BOND in db_bonds:
                datetime_object = datetime.strptime(
                    str(BOND['data_transakcji']), '%Y-%m-%d')
                today = datetime.today() - timedelta(days=datetime_object.day-1)
                month_in_rzymski = rzymskie[today.month-1]

                BOND['ilosc_aktywa'] = int(BOND['ilosc_aktywa'])
                URL = BOND['strona_do_sledzenia']
                BOND["min_value"] = 100
                BOND["max_value"] = 100
                try:
                    rate = 0
                    try:
                        page = requests.get(URL)
                        soup = BeautifulSoup(page.content, "html.parser")
                        table = soup.find(
                            lambda tag: tag.name == "p" and str(today.year) == tag.text).parent.parent
                        column = table.find(
                            lambda tag: tag.name == "th" and month_in_rzymski == tag.text)
                        column_index = table.find('thead').find(
                            'tr').find_all().index(column)
                        row = table.find('tbody').find_all(
                            'tr')[today.day-1]
                        rate = float(row.find_all()[column_index].text)
                    except:
                        bonds_info += f"""
                        <h3 style="color:red; font-weight: bold;">Nie można odnaleźć wyniku odsetek</h3>
                        """
                    BOND["description"] = None
                    # BOND["description"] = soup.find(
                    #     "div", class_="text-content__box wysiwyg")
                    current_price = (rate + 100)
                    BOND["currnet_price"] = current_price
                    curr_price_all = current_price * BOND["ilosc_aktywa"]
                    ex_rate = 1
                    buy_price = BOND["wycena_w_pln"]
                    BOND['currency'] = 'PLN'
                    BOND_current_balance += curr_price_all
                    BOND_money_invested += buy_price
                    BOND["percentage"] = int(
                        (BOND["currnet_price"]-100)/100)
                    BOND["percentage_zakup"] = clamp(int(
                        (BOND["sredni_kurs"]-100)/(100)), 0, 100)
                    BOND["price_indicator"] = 'EXPENSIVE' if BOND["percentage"] > 60 else 'CHEAP' if BOND["percentage"] < 40 else 'NORMAL'
                    try:
                        cursor.execute(
                            f"""CALL MIGAWKI_dodaj('{BOND['isin']}', {BOND['currnet_price']}, '{BOND["currency"]}', {ex_rate});""")
                        connection.commit()
                        migawki = json.loads(BOND['json_list'])
                        migawki.append({'data': datetime.now().strftime(
                            "%Y-%m-%d"), 'wycena': BOND['currnet_price'], 'waluta': BOND["currency"], 'kurs_do_pln': ex_rate})
                    except:
                        pass

                    createPlots(BOND)

                    bonds_info += info_builder(BOND["nazwa_aktywa"], BOND["isin"], BOND["description"], BOND["strona_do_sledzenia"], BOND["ilosc_aktywa"], BOND["currency"], BOND["currnet_price"],
                                               curr_price_all, buy_price, ex_rate, BOND["min_value"], BOND["max_value"], BOND["percentage"], BOND["price_indicator"], BOND["sredni_kurs"], BOND["percentage_zakup"])
                except Exception as e:
                    print(f"Nie można odnaleźć wyniku odsetek: {e}")
                    pass

            # BALANCE SUMARY
            current_balance = ETF_current_balance + \
                shares_current_balance + GOLD_current_balance + BOND_current_balance
            money_invested = ETF_money_invested + shares_money_invested + \
                GOLD_money_invested + BOND_money_invested
            try:
                cursor.execute(
                    f"""CALL MIGAWKI_dodaj('Portfel',{current_balance}, 'PLN', 1);""")
                connection.commit()
            except:
                pass

            cursor.execute("""CALL `AKTYWA_pobierzWszystkiePortfele`();""")
            db_portfele = cursor.fetchall()
            internalFileName = '%s-%s' % (
                datetime.now().strftime('%Y%m%d%H%M%S'), uuid.uuid4())
            createPlots(db_portfele[0], False)
            try:
                fp = open(
                    f'images/{db_portfele[0]["nazwa_aktywa"]}.png', 'rb')
                msgImage = MIMEImage(fp.read())
                fp.close()
                msgImage.add_header('Content-ID', f'<{internalFileName}>')
                msg.attach(msgImage)
            except:
                print('no image')
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
                {table_row_builder('Golds', GOLD_current_balance, GOLD_money_invested)}
                {table_row_builder('Bonds', BOND_current_balance, BOND_money_invested)}
                <tr>
                    <td style="font-weight: bold; font-size: 30px;line-height: 30px;">SUMMARY:</td>
                    <td style="padding: 0 50px;font-weight: bold; font-size: 30px;line-height: 30px;">
                        {format(current_balance, '.2f')} PLN <span style="color:{'red' if current_balance<money_invested else 'green'}; font-size: 20px;line-height: 20px;">({'-' if current_balance<money_invested else '+'} { format(100-(current_balance/money_invested)*100,'.2f') if current_balance<money_invested else format((current_balance/money_invested)*100-100,'.2f') if (money_invested > 0 and current_balance > 0) else 0}%)</span><em style="font-size: 20px;line-height: 20px;"> from {format(money_invested, '.2f')} PLN</em>
                    </td>
                </tr>
            </table>
            <img src="cid:{internalFileName}">
            <div>&nbsp;</div><div>&nbsp;</div>
            """

            # EMAIL SEND

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
                {golds_info}
                {bonds_info}
            </body>
            </html>"""

            message_body = MIMEText(html, 'html')
            msg.attach(message_body)
            server.send_message(msg)
            server.quit()
            msg = MIMEMultipart('alternative')
            return current_balance_info + etf_info + shares_info + bonds_info


if __name__ == '__main__':
    app.run()
