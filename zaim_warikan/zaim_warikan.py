import logging
import os
from datetime import date, timedelta
from pyzaim.pyzaim import ZaimAPI, ZaimCrawler

logger = logging.getLogger()

ZAIM_USER_ID = os.environ.get('ZAIM_USER_ID')
ZAIM_USER_PASSWORD = os.environ.get('ZAIM_USER_PASSWORD')
ZAIM_CONSUMER_ID = os.environ.get('ZAIM_CONSUMER_ID')
ZAIM_CONSUMER_SECRET = os.environ.get('ZAIM_CONSUMER_SECRET')
ZAIM_ACCESS_TOKEN = os.environ.get('ZAIM_ACCESS_TOKEN')
ZAIM_ACCESS_TOKEN_SECRET = os.environ.get('ZAIM_ACCESS_TOKEN_SECRET')
ZAIM_OAUTH_VERIFIER = os.environ.get('ZAIM_OAUTH_VERIFIER')
PERSON_A = os.environ.get('PERSON_A')
PERSON_B = os.environ.get('PERSON_B')
ORIGINAL_CATEGORY_NAME = os.environ.get('ORIGINAL_CATEGORY_NAME', '立替')
ORIGINAL_GENRE_NAME_FORMAT = os.environ.get('ORIGINAL_GENRE_NAME_FORMAT', '%sが%sの代わりに払った分')
KYURYOBI = int(os.environ.get('KYURYOBI', 25))

api = ZaimAPI(
        ZAIM_CONSUMER_ID,
        ZAIM_CONSUMER_SECRET,
        ZAIM_ACCESS_TOKEN,
        ZAIM_ACCESS_TOKEN_SECRET,
        ZAIM_OAUTH_VERIFIER,
)


def month_date(dt: date = None) -> tuple[date, date]:
    today = date.today()
    if dt:
        today = dt
    current_month_end_date = date(today.year, today.month, KYURYOBI)
    while current_month_end_date.weekday() >= 5:
        current_month_end_date = current_month_end_date - timedelta(days=1)
    current_month_end_date = current_month_end_date - timedelta(days=1)
    if today > current_month_end_date:
        # 月末あたりの場合
        start_date = current_month_end_date + timedelta(days=1)
        # 1ヶ月先の計算がめんどいので20日足してよしなにやる
        next_start_date = (start_date + timedelta(days=20)).replace(day=KYURYOBI)
        while next_start_date.weekday() >= 5:
            next_start_date = next_start_date - timedelta(days=1)
        end_date = next_start_date - timedelta(days=1)
    else:
        end_date = current_month_end_date
        prev_start_date = (end_date.replace(day=1) - timedelta(days=1)).replace(day=KYURYOBI)
        while prev_start_date.weekday() >= 5:
            prev_start_date = prev_start_date - timedelta(days=1)
        start_date = prev_start_date
    return start_date, end_date


def zaim_warikan(year: int, month: int, day: int) -> str:
    result = {
        PERSON_A: 0,
        PERSON_B: 0,
    }
    start_date, end_date = month_date(date(year, month, day))
    result_txt = f"**{start_date} ~ {end_date}**\n"
    params = {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
    }
    data = api.get_data(params=params)
    for d in data:
        if d['category_id'] == 0:
            # 振替は無視
            continue
        d['category_name'] = api.category_itos[d['category_id']]
        d['genre_name'] = api.genre_itos[d['genre_id']]
        amount = int(d['amount'])
        if d['category_name'] == ORIGINAL_CATEGORY_NAME:
            if d['genre_name'] == ORIGINAL_GENRE_NAME_FORMAT % (PERSON_A, PERSON_B):
                result[PERSON_B] += amount
            if d['genre_name'] == ORIGINAL_GENRE_NAME_FORMAT % (PERSON_B, PERSON_A):
                result[PERSON_A] += amount
            result_txt += f"{d['date']}\t{d['amount']}\t{d['genre_name']}\t{d['comment']}\n"
        else:
            if d['category_name'] == PERSON_A:
                result[PERSON_B] += amount / 2
            if d['category_name'] == PERSON_B:
                result[PERSON_A] += amount / 2
            result_txt += f"{d['date']}\t{d['amount']}\t{d['category_name']}\t{d['comment']}\n"

    sub = int(abs(result[PERSON_A] - result[PERSON_B]))
    if sub == 0:
        result_txt += "差分はありません"
    elif result[PERSON_A] < result[PERSON_B]:
        result_txt += f"{PERSON_B}が{PERSON_A}に **{sub}** 円払う"
    else:
        result_txt += f"{PERSON_A}が{PERSON_B}に **{sub}** 円払う"
    return result_txt


def _entry_text(dt: date | str, amount: int, genre: str, category: str, comment: str, place: str = "") -> str:
    if amount > 0:
        # income
        txt = f"{dt}\t{amount}\t{genre}\t{place}\n"
    elif category in [PERSON_A, PERSON_B]:
        # 手入力
        txt = f"{dt}\t{amount}\t{category}\t{genre}\t{comment}\n"
    else:
        txt = f"{dt}\t{amount}\t{genre}\t{comment}\t{place}\n"
    return txt


def zaim_warikan_scrape(year: int, month: int, diff_only: bool = False) -> str:
    # https://github.com/SeleniumHQ/docker-selenium/issues/1605 によりdocker-seleniumが300秒でsessionを殺すので、都度crawler(driver)を作成する
    crawler = ZaimCrawler(ZAIM_USER_ID, ZAIM_USER_PASSWORD, driver_path='remote', headless=True, poor=True)
    result = {
        PERSON_A: 0,
        PERSON_B: 0,
    }
    start_date, end_date = month_date(date(year, month, 1))
    result_txt = f"**{start_date} ~ {end_date}**\n"
    data = crawler.get_data(year=year, month=month)
    for d in data:
        d['date'] = date(d['date'].year, d['date'].month, d['date'].day)
        if d['type'] == 'transfer':
            # 振替は無視
            continue
        amount = int(d['amount'])
        if d['type'] != 'income':
            amount *= -1

        if d['category'] == ORIGINAL_CATEGORY_NAME:
            if d['genre'] == ORIGINAL_GENRE_NAME_FORMAT % (PERSON_A, PERSON_B):
                result[PERSON_B] += amount
            if d['genre'] == ORIGINAL_GENRE_NAME_FORMAT % (PERSON_B, PERSON_A):
                result[PERSON_A] += amount
        else:
            if d['category'] == PERSON_A:
                result[PERSON_B] += amount / 2
            if d['category'] == PERSON_B:
                result[PERSON_A] += amount / 2
        result_txt += _entry_text(d['date'], amount, d['genre'], d['category'], d['comment'], d['place'])

    sub = int(abs(result[PERSON_A] - result[PERSON_B]))
    if sub == 0:
        result_txt += "差分はありません"
    elif result[PERSON_A] > result[PERSON_B]:
        result_txt += f"{PERSON_B}が{PERSON_A}に **{sub}** 円払う"
    else:
        result_txt += f"{PERSON_A}が{PERSON_B}に **{sub}** 円払う"
    # self.driverのデストラクタに任せる
    # self.driver.quit()
    return result_txt


if __name__ == '__main__':
    # print(zaim_warikan(2022, 9, 1))
    print(zaim_warikan_scrape(2022, 9, 1))
