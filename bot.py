import os
import secrets
import threading
import requests

from flask import Flask, request, render_template, jsonify

BOT_TOKEN = os.environ["BOT_TOKEN"]
ADMIN_CHAT_ID = os.environ["ADMIN_CHAT_ID"]
PUBLIC_URL = os.environ["PUBLIC_URL"].rstrip("/")

app = Flask(__name__)

sessions = {}


def telegram(method, data=None, files=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"

    return requests.post(
        url,
        data=data,
        files=files,
        timeout=30
    ).json()


def send_message(text):
    return telegram(
        "sendMessage",
        {
            "chat_id": ADMIN_CHAT_ID,
            "text": text
        }
    )


def send_photo(image, caption):
    return telegram(
        "sendPhoto",
        {
            "chat_id": ADMIN_CHAT_ID,
            "caption": caption
        },
        {
            "photo": (
                "capture.jpg",
                image,
                "image/jpeg"
            )
        }
    )


@app.route("/capture/<token>")
def capture(token):

    if token not in sessions:
        return "Bu link etibarsızdır.", 404

    return render_template(
        "capture.html",
        token=token
    )


@app.route("/upload/<token>", methods=["POST"])
def upload(token):

    if token not in sessions:
        return jsonify({
            "ok": False,
            "error": "Link etibarsızdır."
        }), 404

    image = request.files.get("image")
    kind = request.form.get("kind")

    if not image:
        return jsonify({
            "ok": False,
            "error": "Şəkil göndərilmədi."
        }), 400

    data = image.read()

    if len(data) > 8 * 1024 * 1024:
        return jsonify({
            "ok": False,
            "error": "Şəkil çox böyükdür."
        }), 413

    if kind == "camera":
        caption = "📷 İstifadəçinin razılığı ilə kamera görüntüsü"
    else:
        caption = "🖥️ İstifadəçinin razılığı ilə ekran görüntüsü"

    result = send_photo(data, caption)

    if not result.get("ok"):
        return jsonify({
            "ok": False,
            "error": "Telegram-a göndərmək mümkün olmadı."
        }), 500

    return jsonify({
        "ok": True
    })


def generate_link():

    token = secrets.token_urlsafe(24)

    sessions[token] = {
        "admin": ADMIN_CHAT_ID
    }

    return f"{PUBLIC_URL}/capture/{token}"


def bot_loop():

    offset = None

    while True:

        try:

            params = {
                "timeout": 30
            }

            if offset is not None:
                params["offset"] = offset

            response = requests.get(
                f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates",
                params=params,
                timeout=40
            ).json()

            for update in response.get("result", []):

                offset = update["update_id"] + 1

                message = update.get("message", {})

                chat_id = str(
                    message.get("chat", {}).get("id", "")
                )

                text = message.get("text", "")

                if chat_id != str(ADMIN_CHAT_ID):
                    continue

                if text == "/start":

                    send_message(
                        "🤖 Bot aktivdir!\n\n"
                        "/link — yeni paylaşım linki yarat"
                    )

                elif text == "/link":

                    link = generate_link()

                    send_message(
                        "🔗 Link hazırdır:\n\n"
                        f"{link}\n\n"
                        "İstifadəçi kamera və ya ekran "
                        "paylaşımını özü təsdiqləməlidir."
                    )

        except Exception as e:

            print("Bot xətası:", e)


if __name__ == "__main__":

    threading.Thread(
        target=bot_loop,
        daemon=True
    ).start()

    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8080))
    )
