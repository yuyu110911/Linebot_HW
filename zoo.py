# -*- coding: utf-8 -*-
"""
Created on Thu Dec 25 20:31:29 2025

@author: 鬱鬱
"""

import os
from flask import Flask, request, abort, render_template
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from urllib.parse import quote, parse_qsl

from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    PostbackEvent,
    TemplateSendMessage, ButtonsTemplate,
    MessageTemplateAction, URITemplateAction,
    CarouselTemplate, CarouselColumn,
    LocationSendMessage
)

app = Flask(__name__)

# ====== ✅ 改成環境變數 ======
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "")

LIFF_ID_BOOK = os.getenv("LIFF_ID_BOOK", "")
LIFF_ID_CANCEL = os.getenv("LIFF_ID_CANCEL", "")

BASE_URL = os.getenv("BASE_URL", "")  # 例如 https://xxx.onrender.com
baseurl = BASE_URL.rstrip("/") + "/static/"

# ====== ✅ Render Postgres：DATABASE_URL ======
DATABASE_URL = os.getenv("DATABASE_URL", "")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)
db = SQLAlchemy(app)

SHOWS = {
    "凶猛野獸餵食": {"times": ["13:00", "15:30", "18:00"], "duration_min": 40},
    "企鵝體驗館": {"times": ["10:30", "13:30", "15:30", "17:30"], "duration_min": 20},
    "可愛動物探索": {"times": ["11:30", "13:30", "15:30", "17:00"], "duration_min": 45},
    "認識稀有動物": {"times": ["09:00", "10:00", "13:30", "15:30", "17:30"], "duration_min": 30},
}

@app.route("/")
def home():
    return "OK"

@app.route("/show_book")
def show_book():
    pre_show = request.args.get("show", "")
    return render_template("show_book.html", liffid=LIFF_ID_BOOK, shows=SHOWS, pre_show=pre_show)

@app.route("/show_cancel")
def show_cancel():
    return render_template("show_cancel.html", liffid=LIFF_ID_CANCEL)

@app.route("/createdb")
def createdb():
    sql = """
    DROP TABLE IF EXISTS zoo_user CASCADE;
    DROP TABLE IF EXISTS booking CASCADE;

    CREATE TABLE zoo_user (
        id SERIAL PRIMARY KEY,
        uid VARCHAR(50) UNIQUE NOT NULL
    );

    CREATE TABLE booking (
        id SERIAL PRIMARY KEY,
        uid VARCHAR(50) NOT NULL,
        show_name VARCHAR(50) NOT NULL,
        show_time VARCHAR(10) NOT NULL,
        show_date VARCHAR(10) NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (uid, show_name, show_date)
    );
    """
    db.session.execute(text(sql))
    db.session.commit()
    return "資料表建立成功！"

@app.route("/api/bookings")
def api_bookings():
    uid = request.args.get("uid", "")
    rows = db.session.execute(
        text("SELECT id, show_name, show_time, show_date FROM booking WHERE uid=:uid ORDER BY show_date DESC, show_time ASC"),
        {"uid": uid}
    ).fetchall()
    data = [{"id": r[0], "show_name": r[1], "show_time": r[2], "show_date": r[3]} for r in rows]
    return {"ok": True, "data": data}

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)

    print("----- LINE BODY START -----")
    print(body)
    print("----- LINE BODY END -----")

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    except Exception as e:
        print("callback error:", repr(e))
        abort(500)

    return "OK"

def ensure_user(uid: str):
    r = db.session.execute(text("SELECT id FROM zoo_user WHERE uid=:uid"), {"uid": uid}).fetchone()
    if not r:
        db.session.execute(text("INSERT INTO zoo_user(uid) VALUES(:uid)"), {"uid": uid})
        db.session.commit()

def send_use(event):
    text1 = (
        "【動物園演出預約使用說明】\n"
        "1. 點「@演出預約」可選演出/時間並送出。\n"
        "2. 同一個演出內容在同一天只能預約一次。\n"
        "3. 同一天可預約多個不同演出。\n"
        "4. 點「@取消預約」可一次取消一個或多個。"
    )
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=text1))

def send_about(event):
    text1 = (
        "台北市立動物園是親子與自然教育的熱門景點，\n"
        "園區有多種主題館與動物展示，也有演出/導覽活動。\n"
        "歡迎來體驗寓教於樂的動物世界！"
    )
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=text1))

def send_position(event):
    message = LocationSendMessage(
        title="台北市立動物園",
        address="台北市文山區新光路二段30號",
        latitude=24.9985,
        longitude=121.5800
    )
    line_bot_api.reply_message(event.reply_token, message)

def send_contact(event):
    message = TemplateSendMessage(
        alt_text="聯絡我們",
        template=ButtonsTemplate(
            title="聯絡我們",
            text="點擊下方按鈕撥打電話",
            actions=[URITemplateAction(label="撥打電話", uri="tel:0229382300")]
        )
    )
    line_bot_api.reply_message(event.reply_token, message)

def send_show_menu(event):
    try:
        message = TemplateSendMessage(
            alt_text='演出預約轉盤',
            template=CarouselTemplate(
                columns=[
                    CarouselColumn(
                        thumbnail_image_url=baseurl + 'lion.jpg',
                        title='🦁 凶猛野獸餵食',
                        text='活動約 40 分鐘',
                        actions=[
                            URITemplateAction(
                                label='線上預約',
                                uri=f"https://liff.line.me/{LIFF_ID_BOOK}?show={quote('凶猛野獸餵食')}"
                            ),
                            MessageTemplateAction(
                                label='演出介紹',
                                text='近距離觀察猛獸進食行為，飼育員現場解說習性與保育知識。'
                            ),
                        ]
                    ),
                    CarouselColumn(
                        thumbnail_image_url=baseurl + '企鵝.jpg',
                        title='🐧 企鵝體驗館',
                        text='活動約 20 分鐘',
                        actions=[
                            URITemplateAction(
                                label='線上預約',
                                uri=f"https://liff.line.me/{LIFF_ID_BOOK}?show={quote('企鵝體驗館')}"
                            ),
                            MessageTemplateAction(
                                label='演出介紹',
                                text='近距離觀察企鵝活動與游泳模樣，了解牠們的日常與生態特色。'
                            ),
                        ]
                    ),
                    CarouselColumn(
                        thumbnail_image_url=baseurl + 'cute.jpg',
                        title='🐾 可愛動物探索',
                        text='活動約 45 分鐘',
                        actions=[
                            URITemplateAction(
                                label='線上預約',
                                uri=f"https://liff.line.me/{LIFF_ID_BOOK}?show={quote('可愛動物探索')}"
                            ),
                            MessageTemplateAction(
                                label='演出介紹',
                                text='互動導覽認識溫馴小動物的特徵、習性與照護方式。'
                            ),
                        ]
                    ),
                    CarouselColumn(
                        thumbnail_image_url=baseurl + '333.png',
                        title='🦓 認識稀有動物',
                        text='活動約 30 分鐘',
                        actions=[
                            URITemplateAction(
                                label='線上預約',
                                uri=f"https://liff.line.me/{LIFF_ID_BOOK}?show={quote('認識稀有動物')}"
                            ),
                            MessageTemplateAction(
                                label='演出介紹',
                                text='認識平時少見的稀有動物，了解牠們的棲地與保育的重要性。'
                            ),
                        ]
                    ),
                ]
            )
        )
        line_bot_api.reply_message(event.reply_token, message)
    except Exception as e:
        print("send_show_menu error:", repr(e))
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="發生錯誤！"))

def send_cancel_entry(event):
    message = TemplateSendMessage(
        alt_text="取消預約",
        template=ButtonsTemplate(
            title="取消預約",
            text="開啟取消頁面，勾選要取消的預約（可多選）",
            actions=[
                URITemplateAction(
                    label="開啟取消頁面",
                    uri=f"https://liff.line.me/{LIFF_ID_CANCEL}?mode=cancel"
                )
            ]
        )
    )
    line_bot_api.reply_message(event.reply_token, message)

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    try:
        uid = event.source.user_id
        ensure_user(uid)

        mtext = event.message.text.strip()
        print("USER TEXT =", mtext)

        if mtext == "@使用說明":
            send_use(event)
        elif mtext == "@演出預約":
            send_show_menu(event)
        elif mtext == "@取消預約":
            send_cancel_entry(event)
        elif mtext == "@關於我們":
            send_about(event)
        elif mtext == "@位置資訊":
            send_position(event)
        elif mtext == "@聯絡我們":
            send_contact(event)

        elif mtext.startswith("###BOOK/"):
            try:
                _, show_name, show_date, show_time = mtext.split("/", 3)
                db.session.execute(
                    text("""
                        INSERT INTO booking(uid, show_name, show_time, show_date)
                        VALUES(:uid, :show_name, :show_time, :show_date)
                    """),
                    {"uid": uid, "show_name": show_name, "show_time": show_time, "show_date": show_date}
                )
                db.session.commit()
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text=f"✅ 預約成功！\n演出：{show_name}\n日期：{show_date}\n時間：{show_time}")
                )
            except Exception as e:
                print("BOOK ERROR:", repr(e))
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text="⚠️ 預約失敗：同一個演出內容在同一天只能預約一次。")
                )

        elif mtext.startswith("###CANCEL/"):
            try:
                ids_str = mtext.replace("###CANCEL/", "").strip()
                ids = [int(x) for x in ids_str.split(",") if x.strip().isdigit()]
                if not ids:
                    line_bot_api.reply_message(event.reply_token, TextSendMessage(text="你沒有選擇任何要取消的預約。"))
                    return

                db.session.execute(
                    text("DELETE FROM booking WHERE uid=:uid AND id = ANY(:ids)"),
                    {"uid": uid, "ids": ids}
                )
                db.session.commit()
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"✅ 已取消 {len(ids)} 筆預約。"))
            except Exception as e:
                print("CANCEL ERROR:", repr(e))
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text="⚠️ 取消失敗，請稍後再試。"))

    except Exception as e:
        print("handle_message error:", repr(e))
        try:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="系統忙碌中，請稍後再試。"))
        except:
            pass

@handler.add(PostbackEvent)
def handle_postback(event):
    backdata = dict(parse_qsl(event.postback.data))
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=str(backdata)))

if __name__ == "__main__":
    app.run()